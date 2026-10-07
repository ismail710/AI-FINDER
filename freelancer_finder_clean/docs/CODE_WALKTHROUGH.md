# Code walkthrough

## Configuration

`src/freelancer_finder/config.py` loads `.env` once and exposes an immutable
`settings` object. Centralizing configuration avoids one module using a different
model, timeout, or database path from another.

## Data layer

`data/database.py`

- `initialize_database()` applies `data/schema.sql`.
- `database_session()` opens SQLite with named-row access, foreign keys, commit,
  rollback, and guaranteed close behavior.

`data/seed.py` inserts repeatable fictional freelancers and four projects per
profile. It is maintenance code, not imported by request handling.

`data/memory.py`

- Validates or creates opaque conversation IDs.
- `save_exchange()` stores one successful user/assistant pair atomically.
- `load_messages()` returns a bounded transcript in chronological order.

## Embedding layer

`embeddings/profiles.py`

- `build_profile_text()` joins only the requested profile columns into labeled
  text. One call creates one vector for one freelancer.
- `create_profile_embedding()` returns the freelancer ID, source text, model,
  dimensions, and vector together so ownership cannot be lost.
- `refresh_profile_embeddings()` loops over profiles and upserts one row per
  freelancer and embedding model.

`embeddings/projects.py` joins all public project descriptions for each
freelancer and stores that combined portfolio vector in
`project_embedding_json`. Profile and project vectors remain separate so the
search can expose both scores.

## Matching layer

`matching/planner.py`

- Defines strict Pydantic models for the LLM's planning output.
- `create_search_plan()` converts a goal and conversation history to a route and
  search brief.
- `constraint_arguments()` prevents inferred preferences from becoming hard
  filters and rejects constraints with no user-message provenance.
- The `complete_explicit_*` helpers repair narrowly defined omissions from
  verbatim user wording; they never infer a constraint from a project theme.
- `apply_latest_rate_correction()` turns conversational corrections such as
  “more than 60 dollars” into a minimum rate and removes the previous maximum.
- Unknown profession names are not forced into exact database work-field labels.
- `remove_satisfied_followups()` stops the answer from asking users to reconfirm
  availability, rate, currency, location, or skills already checked in SQL.
- `structured_response()` gives the LLM only one schema-repair attempt.

`matching/search.py`

- `match_freelancers()` embeds the client request, applies basic SQL filters,
  computes profile/project cosine scores, and ranks records.
- `verify_candidate_batch()` reloads exact database fields and public projects,
  then checks mandatory skills and other explicit constraints.
- `verified_semantic_search()` widens the candidate batch until it has enough
  passing records or has checked all eligible rows.
- `adaptive_verified_semantic_search()` always tries the complete request first.
  If zero candidates pass, it reuses the same semantic ranking while testing
  one-constraint alternatives in a fixed order.
- `constraint_relaxation_variants()` never removes more than one condition at a
  time and never relaxes currency independently.

`matching/review.py`

- Builds a compact evidence packet from the verified records.
- Requires a structured review decision from the LLM.
- Marks every controlled fallback as a partial near match and adds the requested
  versus actual value to its evidence gaps.
- Refines the semantic query only when evidence is weak and the next query is
  meaningfully different.
- Produces an honest no-fit result when neither the exact search nor a disclosed
  one-constraint fallback has relevant evidence.

## Agent layer

`agent/service.py` creates the model and tools and exposes two entry points:

- `run_agent()` handles direct `match`, direct `sql`, or ordinary tool-driven
  agent execution.
- `run_reviewed_agent()` is the main application path. It creates a plan,
  selects the route, runs the review loop for matches, and returns answer text
  plus machine-readable metadata for the UI.

The SQL engine is read-only. The semantic tool returns JSON so the agent cannot
confuse formatted prose with database evidence.

## Web layer

`web/server.py` uses Python's standard HTTP server so the demo has no framework
dependency. It exposes `/api/chat`, `/api/match`, `/api/sql`, and `/api/status`.
`web/static/index.html` is the complete browser client.

The web layer also exposes a read-only conversation-message endpoint for page
restoration. Basic “what did I ask?” requests are answered deterministically;
normal follow-ups are passed to the planner with the recent stored transcript.

## Maintenance scripts

- `scripts/setup_database.py`: initialize and seed sample data.
- `scripts/refresh_embeddings.py`: rebuild profile and project vectors.
- `scripts/inspect_database.py`: print counts and a readable five-row sample.
- `scripts/start_ollama.cmd`: start an isolated local Ollama service.

`run.cmd` and `test.cmd` set `PYTHONPATH` for users who want to run directly from
a cloned folder. For development, `python -m pip install -e .` is also supported.
