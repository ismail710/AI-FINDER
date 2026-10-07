# Architecture

## Request flow

```text
Browser / API caller
        |
        v
web/server.py  -- validates input and loads the conversation's recent history
        |
        +---- data/memory.py <----> SQLite conversation tables
        |
        v
agent/service.py -- calls the planner and selects a bounded route
        |
        +---------------- SQL fact ----------------+
        |                                          v
        |                              read-only LangChain SQL tools
        |
        `---------------- match -------------------+
                                                   v
matching/search.py -- HF query vector + cosine ranking + SQL constraints
                                                   |
                                                   v
matching/review.py -- LLM assesses evidence and requests a better search if needed
                                                   |
                                                   v
answer with candidates, evidence gaps, and clarification questions
```

SQLite is the source of truth. Embeddings decide which records should be
examined first; they do not create facts and do not prove ability.

## Conversation memory

Conversation text is persisted in SQLite, while only the newest messages are
included in each LLM prompt. Validated hard constraints are also stored as a
separate per-conversation snapshot with their verbatim user source quotes. The
planner receives that snapshot on every turn and carries each requirement forward
until the user explicitly replaces or removes it.

The browser creates a random conversation ID and saves only that ID in local
storage. For every successful `/api/chat` request, the server atomically stores
the user message and assistant answer in SQLite. The next request loads the last
10 messages for planning; page startup can load the last 50 for display.

Simple recall requests such as “What was my previous question?” use a
deterministic route instead of asking the LLM to interpret its own history.
**New chat** rotates the browser to a new ID; it does not silently mix threads.

## Predictable routing

`matching/planner.py` asks the LLM for a strict `SearchPlan` JSON object. Its
route is one of:

- `match`: a project goal or candidate recommendation.
- `sql`: a factual count, named record lookup, or database comparison.
- `clarify`: the intended outcome is too ambiguous to select a profession.
- `conversation`: a greeting or a general discussion without a database task.

The planner infers likely professions, useful skills, relevant portfolio
evidence, and follow-up questions. Inferred ideas stay in the semantic query.
Only requirements explicitly written by the user become hard SQL constraints.
Each hard constraint must carry a verbatim `source_quote`; the application
validates that quote against user messages before using it.

Two narrow normalizers make small local-model output reliable without guessing:

- A phrase such as `with Django skills` preserves `Django` as an explicit skill
  constraint even when the planner omits that JSON field.
- If the planner extracts `60` from `60 USD per hour` but omits its separate
  currency field, `USD` is recovered from the same verbatim quote. Currency
  symbols or ambiguous wording are not guessed.

Follow-up questions that merely repeat already-verified SQL constraints are
removed before the answer is rendered.

Rate corrections are directional. `under 60 USD per hour` produces a maximum;
a later `more than 60 dollars` replaces it with a minimum while retaining the
earlier profession, availability, skills, and USD context. Unknown profession
labels stay in semantic retrieval instead of becoming invalid exact work-field
filters.

This separation prevents a model guess such as “React would be helpful” from
silently becoming `required_skills = React` and excluding otherwise useful
candidates.

## The bounded review loop

The matching loop is implemented in `matching/review.py`:

1. Preserve the validated constraints as the original request and search with
   all of them first.
2. Retrieve a broad ranked candidate list using profile and public-project
   embeddings, then verify the exact fields in SQLite.
3. If nobody passes, test predictable alternatives that remove exactly one
   condition at a time. The query vector is reused, so these checks require no
   additional embedding call.
4. Prefer relaxations in this order: `available` to `partial`, any availability,
   maximum rate, minimum rate, location, exact work field, then one required skill. Currency is never
   relaxed independently because raw rates in different currencies are not
   comparable.
5. Label every fallback result as a partial near match, preserve all other
   constraints, and show both the requested and actual conflicting value.
6. Load the candidates' profile, skills, bio, and public projects from SQLite,
   then ask the LLM for a strict evidence assessment.
7. If the reviewer requests a different semantic query, repeat the same exact-
   first and one-relaxation policy. The LLM cannot choose hidden relaxations.
8. Stop after the configured retry limit, on a repeated query, or when there is
   no meaningful improvement.

The loop is deliberately bounded (`HF_REVIEW_MAX_RETRIES`, maximum 3). It cannot
run forever or repeatedly spend tokens on the same search. When accepted, the
answer distinguishes strong evidence, partial evidence, and gaps that the client
should confirm in an interview.

## Provider responsibilities

- **Ollama / Qwen**: understands the request, produces structured plans, reviews
  retrieved evidence, and writes the response.
- **Hugging Face inference**: turns text into numeric embedding vectors using
  `sentence-transformers/all-MiniLM-L6-v2` by default.
- **SQLite**: stores profiles, public projects, vectors, and factual constraints.

These responsibilities are independent. Changing the chat model does not
require rebuilding embeddings; changing the embedding model does.

## Safety and evidence boundaries

- The agent's SQL connection has `PRAGMA query_only = ON`.
- Only the maintenance scripts write schema, seed data, or embeddings.
- Private projects are never used as public portfolio evidence.
- Similarity scores are ranking signals, not probability or credential scores.
- “Verified” in code means checked against stored database fields, not externally
  verified identity, licenses, employment, or project outcomes.
