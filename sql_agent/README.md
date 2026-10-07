# SQL agent: freelancer database

`freelancer.sqlite3` is a local SQLite database with `freelancers` and
`projects` tables. No external database service is required.

## Hugging Face setup

The SQL agent uses Hugging Face Inference Providers rather than OpenAI. Create
`sql_agent/.env` from the example, then add an access token that is permitted
to call Inference Providers:

```powershell
Copy-Item sql_agent/.env.example sql_agent/.env
```

`HF_MODEL` is optional; it defaults to `Qwen/Qwen3.8-27B`. The chosen
model and provider must support tool calling for the SQL agent to query the
database.

Initialize it from the repository root:

```powershell
python sql_agent/database.py
```

Use the shared connection helper in Python:

```python
from sql_agent.database import database_session, initialize_database

initialize_database()

with database_session() as connection:
    rows = connection.execute(
        "SELECT id, name, skills_json FROM freelancers WHERE availability_status = ?",
        ("available",),
    ).fetchall()
```

Keep the human-readable history in `task_history.md` current as work is completed.

Populate the local database with 36 freelancers and 144 portfolio projects:

```powershell
python sql_agent/seed_data.py
```

## Project embeddings

With `HF_TOKEN` configured in `sql_agent/.env`, add or refresh one combined
embedding of each freelancer's public projects:

```powershell
python -m sql_agent.embed_projects
```

The `freelancer_embeddings` table keeps the existing profile vector in
`embedding_json` and the separate project vector in `project_embedding_json`.
`project_contents` stores the exact project text sent to the embedding model.
Both vectors use `sentence-transformers/all-MiniLM-L6-v2`.

Preview the saved rows from CMD or PowerShell:

```powershell
python -c "import sqlite3; c=sqlite3.connect('sql_agent/freelancer.sqlite3'); print(*c.execute('SELECT freelancer_id, substr(project_contents, 1, 80), substr(project_embedding_json, 1, 100) FROM freelancer_embeddings LIMIT 5'), sep='\n'); c.close()"
```

## Match a client request

Run a semantic search against both saved vectors:

```powershell
python -m sql_agent.match_freelancers "I need a Python developer to build a Django API backed by PostgreSQL" --top 5
```

The command embeds the request with the same model, computes cosine similarity
against each freelancer's profile and public-project vectors, then ranks by
their average. Scores range from -1 to 1; higher means more similar. When a
freelancer has no project vector, the profile score is used alone. The sample
database contains fictional freelancers and projects, so its rankings are for
testing the workflow.

## Combined SQL and embedding agent

The same search tool is now available to the chat agent. Choose a route
explicitly when you want guaranteed tool selection:

```powershell
# Default: the agent can choose semantic search and/or SQL tools
python -m sql_agent.agent "Find an available Python developer for a Django API"

# Force semantic matching; hard constraints are checked against SQLite
python -m sql_agent.agent "Python developer for Django API" --mode match --availability-status available --max-hourly-rate 60 --currency USD --required-skill Python

# Force factual database lookup; the semantic tool is not available in this mode
python -m sql_agent.agent "How many freelancers are available?" --mode sql

# Ask the LLM to review the draft and retry when it finds a fixable gap
python -m sql_agent.agent "Find an available Django developer under 60 USD/hour" --review
```

`auto` first asks the LLM for a typed, domain-neutral search plan. The model
infers relevant professions, useful skills, portfolio evidence, and criteria
from the client's goal in any field. Inferred items improve semantic retrieval;
only requirements explicitly stated by the user become SQL filters. With no
location constraint, the search covers every location stored in the database.
Candidate recommendations must cite real profile or public-project evidence.
See [INTELLIGENT_MATCHING_ARCHITECTURE.md](INTELLIGENT_MATCHING_ARCHITECTURE.md)
for the complete flow, loop, safeguards, and model comparison.
The semantic tool embeds the request once and ranks saved profile/project
vectors by cosine similarity. It checks candidates in score order against
parameterized SQL constraints (availability, field, rate/currency, and
location), plus any `--required-skill` values found in freelancer or public
project skill data. If a batch does not produce enough verified matches, it
widens the next batch; it stops after finding `--top` matches or exhausting all
candidates. The CLI reports its status, number of batches, and candidates
examined. `partial` means some—but fewer than requested—candidates passed;
`no_verified_matches` means none passed. Required skills are exact
case-insensitive matches, so use them for must-haves rather than preferences.
Similarity is a ranking signal, not a probability of success.

For conversational answers, an LLM reviewer checks the draft against the
request and the tool results. It accepts a supported answer or requests a
specific improvement, optionally asking the agent to use semantic matching or
SQL again. The agent preserves hard requirements and stops after at most two
extra attempts by default. Set `HF_REVIEW_MAX_RETRIES` to 0-3 in `.env` to
change that bound. The CLI uses this behavior with `--review`; the browser
Chat tab uses it automatically. The review adds Hugging Face calls and may
increase response time. If the reviewer rejects an answer and a retry fails,
the chatbot reports that it could not verify the answer instead of showing
the rejected claim. Exact fixed SQL counts bypass the review. The direct,
verified broad-hiring route also needs no LLM rewrite; its candidate summary
comes only from search results.

## Test in a browser

From CMD or PowerShell in the repository root, start the local page:

```cmd
python -m sql_agent.web_app
```

Open `http://127.0.0.1:8765` in your browser. The default Chat tab lets you
ask for freelancers and continue with follow-up questions in the same page.
It shows whether the agent used semantic matching or SQL and displays the
database-verified candidates and review outcome. New chat clears the browser conversation. The
page also shows database row counts, a semantic matching form with hard
requirements, and a SQL question tab. Match results show verification status, candidates checked, similarity
scores, freelancer details, and a sample public project. The SQL tab calls
fixed SQL for simple freelancer/project counts and the existing SQL agent for
other questions. The page shows the executed query for fixed counts. Semantic
matching and agent-driven SQL questions need `HF_TOKEN` configured in
`sql_agent/.env`; the SQLite database also needs saved embeddings for matching.
The agent's SQL connection opens the database read-only; seed and embedding
commands use their separate write connections.
The server listens on your computer only. Press Ctrl+C in the terminal to
stop it. Use `--port 8766` if port 8765 is in use.
Stop and restart an older server to load code changes; refreshing the browser
alone does not reload Python code.

## Run with a local LLM from CMD

If Hugging Face chat credits are unavailable, keep `HF_TOKEN` configured for
semantic embeddings and run planning/review locally with Ollama. In the first
CMD window:

```cmd
cd /d E:\AI-FINDER
set OLLAMA_MODELS=E:\AI-FINDER\.ollama_models
set OLLAMA_HOST=127.0.0.1:11435
set OLLAMA_MAX_TRANSFER_STREAMS=1
"C:\Users\ismmo\AppData\Local\Programs\Ollama\ollama.exe" serve
```

In a second CMD window, install the model once, then start the page:

```cmd
cd /d E:\AI-FINDER
set OLLAMA_HOST=http://127.0.0.1:11435
"C:\Users\ismmo\AppData\Local\Programs\Ollama\ollama.exe" pull qwen3:4b
set LLM_PROVIDER=ollama
set OLLAMA_MODEL=qwen3:4b
set OLLAMA_BASE_URL=http://127.0.0.1:11435
set OLLAMA_TIMEOUT_SECONDS=180
python -m sql_agent.web_app --port 8770
```

Open `http://127.0.0.1:8770`. The page's status badge identifies the active
LLM provider and model. `qwen3:0.6b` is useful only for a quick smoke test; it
is too small for dependable portfolio-evidence review in this application.
