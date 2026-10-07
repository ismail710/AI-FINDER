# Freelancer Finder

An evidence-grounded freelancer recommendation demo. A client describes a goal,
the application converts it into a search plan, ranks stored profiles and public
portfolio projects with embeddings, checks explicit requirements in SQLite, and
uses an LLM to review the evidence before answering.

The conversational search always tries every explicit requirement first. If no
record passes, it can test one constraint change at a time and return the first
useful alternative as a clearly labelled partial near match. It never presents a
relaxed condition as satisfied.

The included records are deterministic **sample data**, not real people. A
recommendation means that the stored evidence is relevant; it does not verify a
person's identity, credentials, or future performance.

## Conversation memory

The chatbot remembers previous questions in the current conversation. The
browser keeps a random conversation ID in local storage, while messages are
stored in the local SQLite database. Reloading the page restores up to 50 visible
messages; the latest 10 messages are supplied to the LLM so prompts stay bounded.
Validated hard requirements are stored separately, so active location, hourly
rate, currency, availability, work-field, and required-skill constraints survive
after their original messages leave that 10-message window. A later explicit
correction or removal replaces the saved value.

Clicking **New chat** creates a separate empty conversation. This demo has no
user authentication, encryption, or retention policy, so production deployments
must add those controls before storing private client conversations.

## What is separated

```text
freelancer_finder_clean/
|-- data/                         SQLite database and schema
|-- docs/                         Architecture, API, and code guide
|-- scripts/                      Database and embedding maintenance
|-- src/freelancer_finder/
|   |-- agent/                    LLM/tool orchestration
|   |-- data/                     SQLite access, sample seeding, chat memory
|   |-- embeddings/               Profile and portfolio vector creation
|   |-- matching/                 Planning, retrieval, verification, review
|   `-- web/                      HTTP API and browser UI
|-- tests/                        Unit and workflow tests
|-- run.cmd                       Start the web application
`-- test.cmd                      Run all tests
```

All runtime configuration is read in one place: `src/freelancer_finder/config.py`.
The browser, command-line tools, tests, and maintenance scripts use the same
database and settings.

## Quick start from Windows CMD

Requirements: Python 3.11 or newer, Ollama, and a Hugging Face token with access
to the inference API used for embeddings.

```bat
cd /d path\to\freelancer_finder_clean
python -m pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`, add `HF_TOKEN`, and keep the Ollama settings as supplied. Start the
local LLM in the first CMD window:

```bat
cd /d path\to\freelancer_finder_clean
scripts\start_ollama.cmd
```

The first time only, open a second CMD window and download the model:

```bat
set OLLAMA_HOST=http://127.0.0.1:11435
ollama pull qwen3:4b
```

Then start the application:

```bat
cd /d path\to\freelancer_finder_clean
run.cmd --port 8780
```

Open <http://127.0.0.1:8780>. Try prompts such as:

- `I want to build a booking website for a dental clinic.`
- `Find an available designer in Portugal under 45 EUR per hour.`
- `How many freelancers are in the database?`
- `I need a physical house designed and built.`

The first match may take longer because the application calls the embedding API
and the local LLM performs planning and evidence review.

## Database and embeddings

This folder already contains a ready-to-query sample database. To rebuild it:

```bat
cd /d path\to\freelancer_finder_clean
set PYTHONPATH=%CD%\src
python scripts\setup_database.py
python scripts\refresh_embeddings.py
python scripts\inspect_database.py
```

`refresh_embeddings.py` creates one profile vector per freelancer from selected
profile columns and stores the `freelancer_id` beside it. It also creates one
combined portfolio vector from that freelancer's public projects. Full vectors
are intentionally not printed by the inspection script because each contains
hundreds of floating-point values.

## Tests

```bat
cd /d path\to\freelancer_finder_clean
test.cmd
```

## LLM evaluation

The project includes 20 realistic English and French conversations covering
vague requests, corrections, explicit constraints, persistent requirements,
and database no-fit cases. Run the planner benchmark with:

```bat
set PYTHONPATH=%CD%\src
python scripts\evaluate_llm.py
```

Add `--full` to include embedding retrieval and evidence review. The report
measures valid structured output, routing, role/skill intent coverage,
constraint accuracy, no-fit accuracy, and elapsed time.

## More documentation

- [Architecture](docs/ARCHITECTURE.md) explains routing and the bounded LLM loop.
- [Visual architecture](docs/ARCHITECTURE_VISUAL.md) contains detailed system,
  sequence, matching-loop, memory, runtime, and database diagrams.
- [Code walkthrough](docs/CODE_WALKTHROUGH.md) maps behavior to functions/files.
- [HTTP API](docs/API.md) gives requests and response shapes.
- [Database](docs/DATABASE.md) explains tables and stored embedding columns.
