# SQL agent task history

This is the append-only human-readable history for SQL-agent work. Keep this
file updated when a task starts, changes, or completes. Do not use `tasks.md`
for status updates.

| Date | Status | Task | Details |
| --- | --- | --- | --- |
| 2026-09-26 | Done | Create the freelancer SQLite database | Created `freelancer.sqlite3` with foreign-key enforcement. |
| 2026-09-26 | Done | Add Python database connection helpers | Added reusable connection, transaction, initialization, and task-update helpers. |
| 2026-09-26 | Done | Create the freelancer and project schema | Added `freelancers` and `projects` tables. |
| 2026-09-26 | Done | Seed sample data | Inserted 36 freelancers and 144 portfolio projects; database integrity check passed. |
| 2026-09-26 | Done | Resolve LangChain SQL toolkit import | Added SQL-agent dependencies and installed `langchain-community` in the active Python 3.12 interpreter. |
| 2026-09-26 | Done | Connect the LangChain SQL instance | Added `sql_database`, connected to the local `freelancer.sqlite3` database. |
| 2026-09-26 | Done | Remove SQL-agent task-update table | Removed `agent_task_updates`; task status is kept in this file. |
| 2026-09-26 | Done | Resolve LangChain OpenAI import | Added and verified `langchain-openai` in the active Python 3.12 interpreter. |
| 2026-09-26 | Done | Resolve LangChain create-agent reference | Added `langchain`, imported `create_agent`, and verified SQL-agent initialization. |
| 2026-09-26 | Blocked | Run the SQL agent | Agent reached OpenAI with `gpt-4o-mini`, but the API account has no remaining credits. |
| 2026-09-26 | Blocked | Run the Hugging Face SQL agent | Hugging Face returned HTTP 403 because `HF_TOKEN` lacks Inference Providers permission. |
| 2026-09-26 | Done | Run the Hugging Face SQL agent | Agent completed a database query using the updated Hugging Face token. |
| 2026-09-26 | Done | Add command-line agent runner | Added a positional-question command for running the SQL agent from a terminal. |
| 2026-09-26 | Done | Bound SQL-agent execution | Added Hugging Face request timeout, recursion limit, SQL-specific instructions, and progress logs to prevent silent hangs. |
| 2026-09-26 | Blocked | Complete a Python-availability agent query | Hugging Face returned four successful responses, but the model did not end the SQL tool loop before the recursion limit. |
| 2026-09-26 | Done | Increase configurable agent recursion limit | Default limit is now 12; set `HF_RECURSION_LIMIT` in `.env` to override it. |
| 2026-09-28 | Done | Build freelancer profile embeddings | Updated `create_embedding` to combine selected row columns into one embedding and retain `freelancer_id` in the record and metadata. |
| 2026-09-28 | Done | Persist freelancer embeddings | Added the `freelancer_embeddings` table and a helper that stores the content, vector JSON, metadata, model, dimensions, and freelancer foreign key. |
| 2026-09-28 | Done | Generate and store profile vectors | Generated 36 real 384-dimensional Hugging Face embeddings and saved them in `freelancer_embeddings`. |
| 2026-09-28 | Done | Add related project vectors | Added project text and project vector columns, migrated the existing SQLite table, and saved one 384-dimensional vector from each freelancer's public projects for all 36 freelancers. |
| 2026-09-28 | Done | Match client requests by embedding similarity | Added a command that embeds a client request, compares it with each saved profile and project vector using cosine similarity, and ranks freelancers. Verified Python development and product design sample requests. |
| 2026-09-29 | Done | Integrate semantic search with SQL agent | Added semantic matching as an agent tool with SQL-side availability, field, rate/currency, and location filters. Added explicit auto, match, and SQL-only CLI routes. |
| 2026-09-29 | Done | Add bounded semantic verification loop | Semantic search now ranks once and checks candidates in widening batches against SQL hard filters and required skills recorded on profiles/public projects; CLI reports status, batches, and examined candidates. |
| 2026-09-29 | Done | Add local browser test page | Added a localhost web page and JSON endpoints for semantic matching, factual SQL questions, and database status; documented the CMD launch command. |
| 2026-09-29 | Done | Correct browser availability count | Browser testing found that the chat model counted all freelancers for an availability question. Added fixed, parameterized SQL for common count questions and showed the query on the page; also loaded the agent token from sql_agent/.env for direct CMD runs. |
| 2026-09-29 | Done | Add freelancer chatbot to browser page | Added a conversational tab with follow-up history and route labels; the chat endpoint uses the existing semantic/SQL agent tools and returns verified match evidence. |
| 2026-09-29 | Done | Make chat SQL connection read-only | Opened the agent database through SQLite mode=ro with query_only; verified reads work and an UPDATE is rejected even after attempting to disable query_only. |
| 2026-09-30 | Done | Add LLM-triggered answer review loop | Added a reviewer that accepts grounded answers or requests a targeted semantic/SQL retry, with a configurable bound and review outcome in the chatbot; added CLI --review and behavior checks. |
| 2026-09-30 | Done | Handle failed quality retries safely | A live reviewer requested SQL correction of a wrong answer, but the provider returned HTTP 402 for the retry. The loop now hides reviewer-rejected answers when retry fails or reaches its limit; the browser shows a concise credits error. |
| 2026-09-30 | Done | Verify LLM-triggered correction end to end | A controlled weak answer claimed 36 available freelancers; the LLM requested a SQL retry, the agent queried the database, and the reviewer accepted the corrected count of 18 after two attempts. |
| 2026-09-30 | Done | Correct broad app-building and hiring requests | Chat now treats "help me build" as project planning, and broad explicit hiring briefs trigger semantic matching directly without inferred exact skill filters. Verified the updated page on port 8766 and added routing tests. |
| 2026-09-30 | Done | Suggest programming freelancers during project intake | An app-building help request now ranks and SQL-checks up to three Software development freelancers, then asks targeted clarification questions. Verified the exact sample prompt in the browser on port 8767 and added success/no-match tests. |
| 2026-09-30 | Done | Stop physical-home requests from matching programmers | Added conservative project-domain routing for physical homes, software, mixed, and unclear requests. Physical-home requests now explain the missing construction category and ask a clarifying question without running semantic search. Verified both home and web-app prompts in the browser on port 8768. |
| 2026-09-30 | Done | Replace domain examples with intelligent search planning | Replaced keyword/domain special cases with a typed LLM search plan for any profession. Added portfolio-evidence validation, immutable user constraints, bounded semantic-query retries, worldwide-by-default search, Qwen3.8-27B as the tested default, and a separate architecture/model guide. |
