# Understanding `agent/service.py`

Source: [service.py](../src/freelancer_finder/agent/service.py).

This guide explains the current code in reading order. `service.py` connects the
application's models, database tools, planner, matching workflow, and answer
reviewer. It is the place where these components are assembled and called.

For example, when a client says “I need a booking website for a dental clinic,”
this module sends the request to the planner, follows its route, and returns an
answer based on the resulting search evidence.

## 1. Imports: what each component provides

| Component | Purpose in this file |
| --- | --- |
| `argparse` | Reads command-line questions and options. |
| `json` | Serializes search results and parses reviewer decisions. |
| `logging` | Records startup, request, review, and failure information. |
| `sqlite3` | Opens SQLite connections in read-only mode. |
| SQLAlchemy `create_engine` and `event` | Manage connections and apply a guard whenever a connection opens. |
| LangChain `create_agent` | Builds agents that can choose and call tools. |
| `HumanMessage` and `AIMessage` | Represent user and assistant messages in returned conversations. |
| `SQLDatabase` and `SQLDatabaseToolkit` | Expose database inspection and querying to the agent. |
| `@tool` | Makes the semantic-search function callable by an LLM agent. |
| `ChatOllama` | Connects to the configured Ollama server. |
| `HuggingFaceEndpoint` and `ChatHuggingFace` | Connect to hosted Hugging Face inference. |
| `settings` | Supplies configuration loaded by `config.py`. |
| `create_search_plan` | Interprets the request and chooses a route. |
| `adaptive_verified_semantic_search` | Retrieves candidates and checks explicit filters against stored data. |
| `run_matching_workflow` | Reviews matching evidence and coordinates matching retries. |

The actual embedding and candidate-ranking implementation lives in other
modules. `service.py` calls those components; it does not calculate vectors itself.

## 2. Startup configuration

Names such as `LLM_PROVIDER`, `OLLAMA_MODEL`, and `HF_MODEL` are copied from
`settings`. This gives the rest of the module consistent model names, URLs,
timeouts, output budgets, and retry limits.

Three output budgets are used:

- `HF_MAX_OUTPUT_TOKENS`: the general agent's budget, despite the historical
  `HF_` prefix. It is also used when the provider is Ollama.
- `PLANNER_MAX_OUTPUT_TOKENS`: the planning response budget.
- `REVIEW_MAX_OUTPUT_TOKENS`: the evidence-review and rewrite budget.

These limit generated output. They do not directly set the model's input context
window or the number of conversation messages retained.

`logging.basicConfig(...)` configures informational log messages. If Hugging Face
is selected without `HF_TOKEN`, startup raises a clear configuration error.

This setup runs when Python imports the module. Importing it initializes the
database schema, constructs model clients, and creates the agents. Changing
settings after import will not rebuild those objects automatically; restarting
the application reloads the configuration.

## 3. SQLite access and write protection

`initialize_database()` first ensures that the database schema exists. That setup
step runs before the read-only adapter is created.

The agent's connections then use two protections:

1. `READ_ONLY_DATABASE_URI` ends with `?mode=ro`. SQLite opens the existing
   database for reading.
2. `_make_agent_connection_read_only()` runs `PRAGMA query_only = ON` whenever
   SQLAlchemy opens a connection. The `@event.listens_for(...)` decorator registers
   this function as the connection hook.

`check_same_thread=False` allows a connection to be used across Python threads;
it does not grant permission to write.

`SQLDatabase(..., include_tables=["freelancers", "projects"])` restricts the
tables exposed through this LangChain adapter. `get_sql_database()` returns the
shared adapter instead of opening a separate one.

The exported `SQLITE_DATABASE_URI` is a conventional database URI. The engine
in this file actually connects through its `creator` callback using
`READ_ONLY_DATABASE_URI`. Separate maintenance components can still use their
own writable connections for seeding and embedding refreshes.

## 4. Model creation: `_create_chat_model(output_tokens)`

This function chooses a chat client from `LLM_PROVIDER`:

| Provider | Client | Output limit | Connection timeout |
| --- | --- | --- | --- |
| `ollama` | `ChatOllama` | `num_predict` | `client_kwargs["timeout"]` |
| `huggingface` | `ChatHuggingFace` wrapping `HuggingFaceEndpoint` | `max_new_tokens` / `max_tokens` | Endpoint `timeout` |

Both branches set `temperature=0` to reduce variation. This encourages consistent
responses but does not guarantee identical output or correct answers. The Ollama
branch also sets `reasoning=False`.

The module creates `model`, `planner_model`, and `review_model` with different
budgets. All three use the same configured provider and model name. Three client
objects do not mean three separately downloaded models or three copies of model
weights in memory.

`hf_endpoint = None` remains for compatibility with older imports. It is not the
active endpoint created inside the Hugging Face branch.

## 5. Tools and agents

`SQLDatabaseToolkit` supplies SQL tools, using the protected database adapter.
`semantic_freelancer_search` supplies the semantic matching tool.

`@tool("semantic_freelancer_search")` exposes the function's name, parameters,
and docstring to LangChain. The docstring explains how the agent should use it.

The semantic tool takes a query and optional filters such as availability,
hourly rate, currency, location, work field, and required skills. Before searching,
it checks `has_explicit_skill_requirement(query)`. If the supplied query does
not state a mandatory skill requirement, `required_skills` is dropped and a
`constraint_notes` explanation is added to the result.

For example, “Build an online shop” can guide relevance ranking toward web and
commerce experience. “Shopify is mandatory” can justify a hard skill filter.
The helper checks the wording supplied to this tool, so this guard is distinct
from the planner's user-message provenance checks.

`adaptive_verified_semantic_search(...)` performs retrieval and database checks.
The tool returns its result as a JSON string. `ensure_ascii=False` preserves
characters such as accented names in that string.

Two agents are constructed:

- `sql_only_agent` receives SQL tools and instructions for factual questions.
- `agent` receives SQL and semantic tools plus `AGENT_SYSTEM_PROMPT`.

The general prompt tells the agent to preserve explicit requirements, avoid
inventing candidate qualifications, disclose near matches, and explain database
limits. Prompts guide model behavior; database guards and Python validation
provide additional controls.

## 6. Entry point: `run_agent(...)`

| Mode | Execution path | Return value |
| --- | --- | --- |
| `match` | Calls `adaptive_verified_semantic_search` directly. | JSON string containing search results. |
| `sql` | Invokes `sql_only_agent` with history and the current question. | Agent result dictionary containing messages. |
| `auto` | Calls `run_reviewed_agent` in automatic mode. | Dictionary containing messages and route-specific metadata. |

Direct `match` mode bypasses the planner and the LLM evidence reviewer. It still
uses verified semantic search, which can disclose a one-constraint fallback.
It passes `required_skills` directly to search, unlike the decorated semantic
tool's wording guard.

`run_agent(..., mode="sql")` does not run the answer-review loop. Use
`run_reviewed_agent(..., mode="sql")` for reviewed SQL answers.

In automatic mode, the planner decides the requirements. The `top` and explicit
filter arguments accepted by `run_agent` are used only by its direct `match`
branch. The CLI enforces that filters belong to `--mode match`.

`AGENT_RECURSION_LIMIT` bounds agent execution steps. It is separate from the
number of answer-review retries.

## 7. Automatic routing: `run_reviewed_agent(...)`

The automatic path follows this structure:

```text
Question + history + confirmed constraints
    -> create_search_plan(planner_model, ..., database_catalog())
        -> sql          -> SQL agent + service.py answer-review loop
        -> clarify      -> planner reply and follow-up questions
        -> conversation -> planner reply and follow-up questions
        -> matching     -> run_matching_workflow in matching/review.py
    -> response dictionary
```

The catalog describes stored categories and other planning metadata. The planner
uses it to produce a structured plan; it does not receive unrestricted SQL access
through this call.

If planning fails, the service returns an assistant message and a review outcome.
It recognizes specific Hugging Face credit-exhaustion messages as
`provider_unavailable`; other planner failures become `planning_unavailable`.

For a `sql` plan, the function calls itself with `mode="sql"`. This delegates to
the SQL branch win, so it is not an infinite recursive loop.

For `clarify` and `conversation`, it combines the planner's reply or goal with
its questions and returns immediately.

For matching, it builds `user_messages` from:

1. Original `source_quote` values attached to confirmed constraints.
2. User turns in the supplied history.
3. The current question.

This preserves the wording needed to justify hard filters. Confirmed constraints
can therefore survive after their original messages leave the prompt history.
This function consumes saved constraints; persistence itself is handled by the
conversation-memory and web layers. `run_agent` does not expose a
`confirmed_constraints` parameter; callers needing it use `run_reviewed_agent`.

The dedicated matching workflow owns candidate evidence review, disclosed
fallbacks, and useful query refinement. Its result is returned under
`matching_result`, while the serialized planner output is returned under
`search_plan`.

## 8. Helpers for reviewing tool-based answers

### `_message_text(content)`

Providers can return a plain string or a list of content blocks. This helper
converts either representation into text so the review code can work with both.
For dictionaries in a content list, it reads their `text` field.

### `_review_evidence(messages)`

This helper extracts tool calls and tool results from an agent conversation.
When a tool result contains a `matches` dictionary, it keeps selected candidate
fields such as names, skills, rates, availability, sample projects, scores,
and the verification flag.

It bounds the review packet with character limits:

- Tool-call arguments: first 1,200 characters.
- Semantic candidates: first five matches.
- Each tool-result entry: first 3,500 characters.
- Combined packet: last 10,000 characters.

These are character limits, not token limits. They reduce prompt size but can
truncate useful evidence. Results that are not recognized semantic JSON are
included as text with truncation. An empty packet becomes
`"No tool evidence was produced."`.

This helper is separate from the candidate evidence packet built inside
`matching/review.py` for the automatic matching workflow.

### `_review_answer(question, answer, messages, history)`

The reviewer receives the current question, draft answer, last six history
messages, and the compact tool evidence. It is asked to accept a supported answer
or identify a specific defect that a retry can fix.

Example decision:

```json
{
  "action": "retry",
  "tool": "sql",
  "feedback": "Check the database count before stating how many freelancers exist."
}
```

The code accepts `action` values `accept` or `retry`, and `tool` values
`semantic`, `sql`, or `none`. It requires string feedback and nonempty feedback
for a retry. Returned feedback is stripped and limited to 500 characters.

It first parses the entire response as JSON. If that fails, it tries the text
between the first opening brace and the last closing brace. Invalid decisions
return `None`.

This helper uses manual JSON validation, not a Pydantic structured-output model.
The prompt requests feedback of at most 50 words and empty feedback with tool
`none` on acceptance; those additional instructions are not fully enforced by
the checks in this function.

## 9. The SQL answer-review loop

After the initial SQL agent answer, `attempts` starts at `1`. The reviewer can
accept the answer or request a correction:

- `sql`: invoke the agent again to obtain relevant database facts.
- `none`: invoke `review_model` to rewrite using supplied evidence. No tools are
  attached to this rewrite call.
- `semantic`: stop with `route_unavailable`, because this path is SQL-only.

The loop compares the new answer and checks whether new messages contain tool
calls. If the answer is unchanged and there are no new tool calls, it stops with
`no_progress`. A new tool call counts as activity here; it does not by itself
prove that stronger evidence was obtained.

`AGENT_REVIEW_MAX_RETRIES` permits that many corrections after the initial
answer. For example, a value of `2` permits up to three answer attempts. The
reviewer can still inspect the last permitted answer before the loop exits.

| Outcome in this loop | Meaning |
| --- | --- |
| `accepted` | The reviewer accepted the current answer. |
| `review_unavailable` | Review raised an error or returned an invalid decision. |
| `retry_limit` | The reviewer requested another correction after the retry budget was used. |
| `route_unavailable` | The reviewer requested semantic search in SQL mode. |
| `retry_failed` | Executing the correction raised an error. |
| `no_progress` | The correction produced the same answer without a new tool call. |

If the latest valid review requested a retry and the final outcome is not
`accepted`, the service appends a message explaining the unresolved problem.
Earlier draft messages remain in the returned history, but the last message is
the limitation message. If review is unavailable before any valid retry verdict,
the original answer remains with `review_unavailable` metadata.

These outcomes belong to the SQL loop. Automatic matching supplies its own
review metadata through `run_matching_workflow`.

## 10. Returned objects

Most conversational paths return a dictionary shaped like this:

```python
{
    "messages": [...],       # LangChain user/assistant/tool messages
    "search_plan": {...},    # Present on successful automatic planning paths
    "matching_result": {...},  # Present on automatic matching paths
    "review": {
        "outcome": "...",
        "attempts": 1,
        "decisions": [...],
    },
}
```

Not every path includes every key. Direct `match` mode returns a JSON string
instead, and plain `sql` mode through `run_agent` returns the agent's result
without the service's review metadata. Consumers usually display the final
message from `result["messages"]`.

## 11. Command-line interface: `main()`

`main()` reads a question, chooses a mode, validates compatible options, and
prints the result. Run these examples from `freelancer_finder_clean` in PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\src"

# Let the planner choose the route; automatic mode already includes review.
python -m freelancer_finder.agent.service "I need a booking website for a dental clinic."

# Ask a factual SQL question and explicitly enable answer review.
python -m freelancer_finder.agent.service "How many freelancers are stored?" --mode sql --review

# Search directly with caller-supplied filters.
python -m freelancer_finder.agent.service "Web developer" --mode match --top 3 --max-hourly-rate 40 --currency EUR --required-skill React
```

These examples require the project's configured services and models to be
available. An Ollama client does not install a missing model automatically.

The CLI rejects structured filters outside `match` mode, rejects `--currency`
without a rate bound, and rejects `--review` with direct `match` mode. `--review`
changes the SQL path; automatic mode already calls `run_reviewed_agent` even
without that flag.

Search output includes names, rates, locations, skills, sample projects, and
similarity scores. A similarity score indicates retrieval relevance, not the
probability that a freelancer will succeed. Conversational output prints the
last message and any available review summary.

## 12. Exports and the entry-point guard

`__all__` declares the intended exports for wildcard imports. It does not prevent
callers from importing other names explicitly. The list includes the shared
models, agents, tools, database adapter, and request functions.

`if __name__ == "__main__": main()` runs the CLI when the module is executed as
a program. Ordinary imports construct the shared objects but do not parse
command-line arguments or run `main()`.

For the wider project structure, see [CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md)
and [ARCHITECTURE.md](ARCHITECTURE.md).
