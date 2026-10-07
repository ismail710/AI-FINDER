# Full SQL and Embedding Agent: Implementation Plan

**Status:** Agent/tool integration implemented; remaining stages awaiting approval  
**Prepared:** 2026-09-29

## Goal

Make one command-line agent answer freelancer questions using both the
structured SQLite database and semantic similarity over saved freelancer
profile and project embeddings.

Example request:

> Find an available Python developer who has built Django APIs, preferably for
> e-commerce clients, under $60/hour.

The agent should combine SQL filters such as availability and hourly rate with
embedding similarity over profile and project content, then explain the matches
using fields and projects actually returned from the database.

## Current project state

- `sql_agent/agent.py` builds a Hugging Face chat model and a LangChain SQL
  toolkit, but the chat agent does not have a freelancer semantic search tool.
- `sql_agent/match_freelancers.py` embeds a prompt and ranks saved profile and
  project vectors by cosine similarity, but it runs independently from the SQL
  chat agent.
- `freelancer_embeddings` stores JSON vectors in SQLite. The current database
  has 36 sample freelancer rows and profile/project vectors for those rows.
- The embeddings use `sentence-transformers/all-MiniLM-L6-v2` through the
  Hugging Face Inference API.
- The freelancer and project rows currently come from seeded fictional data.

## Recommended approach: keep SQLite and rank vectors in Python

For the current 36-freelancer dataset, continue using SQLite for structured
queries and compute cosine similarity over the saved vectors in Python. This
keeps the current database and embedding data, gives exact scoring across every
candidate, and avoids adding a vector database extension before the data volume
requires one.

### Proposed request flow

1. The CLI receives a natural-language question.
2. The agent calls a semantic matching tool for requests that ask for relevant
   freelancers. The tool embeds the request with the same model used to create
   saved vectors.
3. Python scores every candidate with a saved vector against profile and
   project vectors. The combined score is the average of both cosine
   similarities; if a project vector is missing, use the profile score alone.
4. In descending score order, the tool verifies candidates against explicit
   SQL constraints (availability, work field, rate/currency, and location) and
   required skills recorded on freelancer profiles or public projects. If a
   batch does not yield enough verified matches, it expands the batch and
   checks again until it has enough results or exhausts the ranked candidates.
5. The agent returns a short ranked list with separate profile/project scores
   and supporting freelancer/project fields. It should distinguish semantic
   similarity from factual constraints and avoid claiming a skill or project
   unless the database supports it.
6. For factual database questions that do not need semantic matching, the agent
   uses a read-only SQL tool.

### SQL and agent guardrails

- Keep search constraints in parameterized SQL, not SQL fragments generated
  from user text.
- Open the agent's query connection read-only and enable SQLite query-only mode.
- Expose only the freelancer, project, and embedding fields needed to answer
  questions. Keep embedding JSON out of the final response.
- For natural-language SQL questions, allow only read queries, cap returned
  rows, and set a query timeout. Prefer narrow task-specific tools for common
  operations over unrestricted SQL execution.
- Load model clients lazily so importing matching or database helpers does not
  require an unrelated chat-model request.
- Keep `HF_TOKEN` in the local environment file and never print it.

## Alternative implementation approaches

| Approach | How it works | Advantages | Tradeoffs | Fit here |
|---|---|---|---|---|
| SQLite + Python cosine scan | Store JSON vectors in the existing table, fetch eligible rows with SQL, and score every vector in Python. | Lowest migration effort; exact ranking; easy to debug; works with current database. | Reads and scores each eligible vector; cost grows linearly with candidate count. | **Recommended now** for 36 freelancers and a local prototype. |
| SQLite + `sqlite-vec` | Store vectors in a `vec0` virtual table and ask SQLite for nearest neighbors using SQL KNN. | Vector retrieval stays inside SQL and can return nearest neighbors directly. | Adds a native extension and schema/installation work; project describes itself as pre-v1, so breaking changes are possible. SQL filters and joins need careful compatibility checks. | Consider if the project must remain SQLite and vector rows grow substantially. |
| PostgreSQL + `pgvector` | Move data and vector columns to PostgreSQL; rank with cosine distance in SQL, adding HNSW or IVFFlat indexes when needed. | Native vector operators and indexed approximate nearest-neighbor search; SQL joins and filters remain together. | Requires database migration, PostgreSQL service/configuration, data migration, and deployment changes. | Best candidate for a multi-user or deployed production system if PostgreSQL is acceptable. |

All three approaches can use the same Hugging Face embedding model. The
embedding provider and vector storage/search engine are separate choices.

## Implementation stages after approval

1. **Agent/tool integration (implemented):** add a semantic matching tool to
   the existing agent, make routing between semantic matching and SQL factual
   lookup predictable, and add bounded widening batches with database-backed
   verification of hard requirements.
2. **SQL safety and lifecycle:** make agent reads read-only, cap result size,
   configure a timeout, and move model initialization behind the CLI/runtime
   entry point.
3. **Answer grounding:** return ranked candidate evidence with scores and
   project/profile facts; keep raw vectors out of conversational output.
4. **CLI experience:** preserve ordinary database questions and add a clear
   example for similarity matching in the README.
5. **Verification:** run realistic matching and factual questions, verify
   availability/rate filters are honored, verify missing project vectors fall
   back to the profile score, and confirm that attempted database writes are
   rejected.

## Completion criteria

- One command can answer both ordinary SQL questions and freelancer matching
  requests.
- Matching uses the query embedding with the existing profile and project
  vectors from the configured model.
- Explicit SQL constraints are applied before ranking and are visible in the
  returned candidate facts.
- Results include separate profile and project similarity values and grounded
  explanations.
- The conversational agent cannot write to the SQLite database.
- Setup instructions document the model/token requirements and sample commands.

## References

- Hugging Face `InferenceClient.feature_extraction` accepts text or batches of
  text and returns numeric embeddings: [InferenceClient API reference](https://huggingface.co/docs/huggingface_hub/package_reference/inference_client).
- LangChain's SQL agent documentation describes the database-question-answering
  flow and warns that model-generated SQL needs narrowly scoped permissions:
  [LangGraph SQL agent tutorial](https://langchain-ai.github.io/langgraph/tutorials/sql-agent/).
- LangChain's SQL toolkit reference warns that SQL agents may execute arbitrary
  SQL and recommends least-privilege database access:
  [SQL agent toolkit reference](https://reference.langchain.com/python/langchain-community/agent_toolkits/sql/base).
- SQLite supports opening a database with `mode=ro`:
  [SQLite URI filenames](https://www.sqlite.org/uri.html). SQLite's
  `query_only` pragma prevents writes on a connection:
  [SQLite PRAGMA reference](https://sqlite.org/pragma.html#pragma_query_only).
- `sqlite-vec` documents vector storage and KNN-style SQL queries, and notes
  that it is pre-v1: [sqlite-vec repository](https://github.com/asg017/sqlite-vec).
- `pgvector` documents vector columns, cosine distance, exact search, and
  approximate HNSW/IVFFlat indexes: [pgvector repository](https://github.com/pgvector/pgvector).

## Approval and progress

The user approved the agent/tool integration stage. It adds the semantic
matching tool, explicit `auto`, `match`, and `sql` routes, and a bounded
verification loop that widens the semantic candidate batch until enough
database-verified results are found or all candidates are checked. A local
browser chatbot now exposes those routes. Its SQL agent connection uses
SQLite `mode=ro` and `query_only`; the rest of stage 2 (result limits,
timeouts, and lazy model initialization) and later stages remain planned.
The chatbot also has a separate LLM answer-review loop. It can request a
targeted semantic or SQL retry when the answer is materially weak, with two
extra attempts by default and a visible review outcome.
