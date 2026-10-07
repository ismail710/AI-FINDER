# Freelancer Finder: visual architecture

This document explains how the browser, agent, embeddings, SQL verification,
evidence-review loop, and persistent conversation memory work together.

## 1. System context

```mermaid
flowchart LR
    User([Client]) -->|questions and follow-ups| UI[Browser UI<br/>web/static/index.html]
    UI -->|JSON over localhost HTTP| Web[HTTP application<br/>web/server.py]

    Web --> Memory[Conversation memory<br/>data/memory.py]
    Memory --> DB[(SQLite<br/>freelancer.sqlite3)]

    Web --> Agent[Agent service<br/>agent/service.py]
    Agent --> Planner[Structured planner<br/>matching/planner.py]
    Agent --> SQLTools[Read-only SQL tools]
    Agent --> Workflow[Matching workflow<br/>matching/review.py]

    Planner --> Ollama[Ollama<br/>Qwen chat model]
    SQLTools --> DB
    Workflow --> Search[Semantic search<br/>matching/search.py]
    Workflow --> Ollama
    Search --> HF[Hugging Face<br/>embedding inference]
    Search --> DB

    Scripts[Maintenance scripts] -->|seed and refresh| DB
    Scripts -->|create vectors| HF
```

The important boundary is that each component has one responsibility:

- **The LLM understands and reviews.** It creates a structured search plan and
  assesses candidate evidence.
- **Embeddings retrieve.** They rank potentially relevant profiles and projects.
- **SQLite verifies.** Exact skills, availability, rate, currency, location, and
  public portfolio records come from database rows.
- **The web layer remembers.** It loads and saves conversation turns using an
  opaque conversation ID.

Similarity is therefore never treated as proof of professional ability.

## 2. Source-code dependency graph

```mermaid
flowchart TD
    Config[config.py<br/>paths and provider settings]

    DB[data/database.py<br/>connections and schema]
    Seed[data/seed.py<br/>fictional sample records]
    Memory[data/memory.py<br/>conversation persistence]

    Profiles[embeddings/profiles.py<br/>profile vectors]
    Projects[embeddings/projects.py<br/>portfolio vectors]

    Planner[matching/planner.py<br/>route and constraints]
    Search[matching/search.py<br/>rank and SQL verify]
    Review[matching/review.py<br/>bounded evidence loop]

    Agent[agent/service.py<br/>models, tools, orchestration]
    Web[web/server.py<br/>HTTP API]
    Page[web/static/index.html<br/>browser client]

    Config --> DB
    Config --> Memory
    Config --> Profiles
    Config --> Projects
    Config --> Search
    Config --> Agent

    DB --> Seed
    DB --> Memory
    DB --> Profiles
    DB --> Projects
    DB --> Search

    Planner --> Review
    Search --> Review
    Planner --> Agent
    Review --> Agent
    Search --> Agent

    Memory --> Web
    Search --> Web
    Agent --> Web
    Web --> Page
```

There are no imports from the browser into business logic. The browser only
knows the HTTP contract. Matching code can consequently be tested without a
browser, and memory can be tested without an LLM call.

## 3. Complete chat-request sequence

```mermaid
sequenceDiagram
    autonumber
    actor Client
    participant UI as Browser UI
    participant Web as Web server
    participant Mem as SQLite memory
    participant Plan as Planner
    participant LLM as Ollama / Qwen
    participant Match as Matching workflow
    participant HF as HF embeddings
    participant Data as SQLite profiles/projects

    Client->>UI: Submit a question
    UI->>Web: POST /api/chat<br/>message + conversation_id
    Web->>Mem: Load latest 10 messages
    Mem-->>Web: Ordered conversation history

    alt Previous-question recall
        Web->>Web: Deterministic memory answer
    else Simple database count
        Web->>Data: Fixed parameterized SQL
        Data-->>Web: Exact count
    else General question
        Web->>Plan: question + stored history
        Plan->>LLM: Strict SearchPlan JSON schema
        LLM-->>Plan: route, goal, roles, constraints, questions
        Plan->>Plan: Validate user-quote provenance

        alt route = match
            Plan->>Match: Original constraints and fallback policy
            Match->>HF: Embed semantic search text
            HF-->>Match: Query vector
            Match->>Data: Rank once and apply every exact filter
            Data-->>Match: Exact matches or zero rows
            opt zero exact rows
                Match->>Data: Test one-constraint alternatives on same ranking
                Data-->>Match: Labelled near matches or no fit
            end
            Match->>LLM: Review actual profiles and public projects
            LLM-->>Match: Accept, retry with new query, or no fit
        else route = sql
            Plan->>Data: Read-only SQL tools
            Data-->>Plan: Factual rows
        else route = clarify or conversation
            Plan-->>Web: Direct response and useful questions
        end
    end

    Web->>Mem: Atomically save user + assistant messages
    Web-->>UI: Answer, route, evidence, matches, review metadata
    UI-->>Client: Render answer and candidate cards
```

### Why history comes from the server

The browser sends a random `conversation_id`, not the entire transcript. This
prevents accidental duplicate turns and makes a page reload safe. The database
is the authoritative history. For backwards compatibility, API clients without
an ID may still provide an initial `history` array.

## 4. Predictable routing

```mermaid
flowchart TD
    A[Incoming message] --> B{Stored-history recall phrase?}
    B -->|yes| C[Return previous question directly]
    B -->|no| D{Exact supported count question?}
    D -->|yes| E[Run fixed parameterized SQL]
    D -->|no| F[Ask LLM for strict SearchPlan]

    F --> G{Selected route}
    G -->|match| H[Semantic retrieval and evidence review]
    G -->|sql| I[Read-only LangChain SQL agent]
    G -->|clarify| J[Ask up to 3 focused questions]
    G -->|conversation| K[Respond using conversation context]

    H --> L[Save exchange]
    I --> L
    J --> L
    K --> L
    C --> L
    E --> L
```

| Route | Used for | Main evidence source |
|---|---|---|
| `match` | Finding or recommending professionals for a goal | Embedding retrieval plus verified SQL records |
| `sql` | Counts, named records, and factual comparisons | Read-only SQLite queries |
| `clarify` | A goal too ambiguous to choose a profession | Conversation and planner reasoning |
| `conversation` | Greetings, scope discussion, and context questions | Stored conversation history |

The planner never uses an inferred skill as an exact database constraint. A
hard constraint must be traceable to a verbatim user phrase. For example,
`with Django skills` can create a Django constraint; `build a web app with AI`
remains a broad semantic preference.

## 5. Semantic matching and evidence-review loop

```mermaid
flowchart TD
    Start([Validated SearchPlan]) --> Preserve[Preserve original SQL constraints]
    Preserve --> Query[Use initial semantic query]
    Query --> Duplicate{Query already attempted?}
    Duplicate -->|yes| StopNoProgress[Stop: no progress]
    Duplicate -->|no| Embed[Create query embedding]

    Embed --> Rank[Compare with profile and project vectors]
    Rank --> Exact[Apply every requested SQL constraint<br/>while widening candidate batches]
    Exact --> ExactFound{Any exact matches?}
    ExactFound -->|yes| Evidence[Load bio, skills, profession,<br/>and PUBLIC projects]
    ExactFound -->|no| More{Unchecked one-constraint<br/>alternative remains?}
    More -->|yes| Relax[Test next alternative on same ranking<br/>partial/any availability, rate, location, field, skill]
    Relax --> NearFound{Any candidates pass?}
    NearFound -->|no| More
    NearFound -->|yes| MarkNear[Record original, applied, and relaxed<br/>constraints; force partial fit]
    MarkNear --> Evidence
    More -->|no| NoFit[Explain database coverage limit]

    Evidence --> Review[LLM evidence review]
    Review --> Decision{Review decision}
    Decision -->|accept| Render[Render matches, evidence, gaps,<br/>and clarification questions]
    Decision -->|retry with different query| Limit{Retry limit reached?}
    Limit -->|no| Query
    Limit -->|yes| SafeStop[Return incomplete result honestly]
    Decision -->|no supported fit| NoFit

    Render --> Done([Response])
    SafeStop --> Done
    NoFit --> Done
    StopNoProgress --> Done
```

### Loop guarantees

1. Every search tries all original constraints before considering a fallback.
2. A fallback can remove only one condition and keeps every other constraint.
3. Relaxation order is deterministic, and currency is never removed by itself.
4. Every near match is labelled partial and shows the requested versus actual
   value; the LLM cannot hide or add a relaxation.
5. A retry must use a meaningfully different query and repeats the exact-first
   policy.
6. With the default `HF_REVIEW_MAX_RETRIES=2`, there can be at most three search
   attempts: one initial attempt and two revisions.
7. A strong exact match needs actual public-project evidence, not only a high vector
   score.
8. If the evidence is weak, the answer states the gap rather than inventing
   experience.

## 6. How embedding retrieval works

```mermaid
flowchart LR
    subgraph Offline[Maintenance time]
        F[Freelancer columns<br/>name, bio, field, skills,<br/>experience, location, languages]
        P[All public projects<br/>for one freelancer]
        PE[Profile embedding]
        PJE[Combined project embedding]
        F -->|join selected labeled fields| PE
        P -->|join project descriptions| PJE
        PE --> Saved[(freelancer_embeddings)]
        PJE --> Saved
    end

    subgraph Request[Search time]
        Need[Client goal] --> QE[Query embedding]
        QE --> ProfileScore[Cosine similarity<br/>to profile vector]
        QE --> ProjectScore[Cosine similarity<br/>to project vector]
        ProfileScore --> Combined[Average available scores]
        ProjectScore --> Combined
        Combined --> Ranked[Ranked candidate IDs]
        Ranked --> Verify[Reload exact SQL fields<br/>and verify constraints]
    end
```

One embedding row belongs to exactly one freelancer through `freelancer_id`.
`embedding_json` represents the selected profile columns;
`project_embedding_json` represents that person's combined public portfolio.
Both use the same model and dimensions before cosine comparison.

The combined similarity score is:

```text
(profile similarity + project similarity) / 2
```

If no project vector exists, only the profile score is used. Scores rank records;
they are not probabilities of successful delivery.

## 7. Conversation-memory lifecycle

```mermaid
stateDiagram-v2
    [*] --> NewThread: First visit creates random ID
    NewThread --> Active: First successful answer saved
    Active --> Active: Load last 10 messages, answer, save exchange
    Active --> Restored: Browser reload
    Restored --> Active: Load up to 50 messages for display
    Active --> NewThread: User clicks New chat
```

```mermaid
sequenceDiagram
    participant Browser
    participant API
    participant SQLite

    Browser->>Browser: Read conversation ID from localStorage
    Browser->>API: GET /api/conversations/{id}/messages
    API->>SQLite: Select latest 50 messages
    SQLite-->>API: user/assistant rows
    API-->>Browser: Chronological transcript
    Browser->>Browser: Rebuild chat bubbles

    Browser->>API: POST /api/chat with same ID
    API->>SQLite: Select latest 10 messages
    SQLite-->>API: Bounded LLM context
    API->>SQLite: Insert user + assistant atomically
```

Memory is local to this SQLite database. The demo does not include accounts or
access control. A production service must associate conversations with an
authenticated user, encrypt sensitive data, and define deletion/retention rules.

## 8. Database relationship graph

```mermaid
erDiagram
    FREELANCERS ||--o{ PROJECTS : owns
    FREELANCERS ||--o{ FREELANCER_EMBEDDINGS : represented_by
    CONVERSATIONS ||--o{ CONVERSATION_MESSAGES : contains

    FREELANCERS {
        text id PK
        text name
        text bio
        text work_field
        text skills_json
        real hourly_rate
        text currency
        text availability_status
        text location
    }

    PROJECTS {
        text id PK
        text freelancer_id FK
        text title
        text detail
        text skills_used_json
        integer is_public
    }

    FREELANCER_EMBEDDINGS {
        text id PK
        text freelancer_id FK
        text contents
        text embedding_json
        text project_contents
        text project_embedding_json
        text embedding_model
        integer dimensions
    }

    CONVERSATIONS {
        text id PK
        text created_at
        text updated_at
    }

    CONVERSATION_MESSAGES {
        integer id PK
        text conversation_id FK
        text role
        text content
        text created_at
    }
```

The agent's LangChain SQL tools can see only `freelancers` and `projects`, and
their connection has `PRAGMA query_only = ON`. Conversation writes and embedding
maintenance use separate, explicit application functions.

## 9. Runtime and provider boundaries

```mermaid
flowchart TB
    subgraph Machine[Local Windows machine]
        Browser[Web browser]
        Python[Python HTTP server<br/>127.0.0.1:8780]
        Ollama[Ollama service<br/>127.0.0.1:11435]
        SQLite[(Local SQLite file)]

        Browser --> Python
        Python --> Ollama
        Python --> SQLite
    end

    subgraph External[External provider]
        HF[Hugging Face inference API<br/>all-MiniLM-L6-v2]
    end

    Python -->|query embeddings| HF
    HF -->|384-number vector| Python
```

- The chat model and SQL database remain local.
- Text sent for a new embedding query goes to the configured Hugging Face
  inference provider.
- `HF_TOKEN` stays server-side and is never returned by `/api/status`.
- Changing the chat model does not require rebuilding vectors. Changing
  `EMBEDDING_MODEL` does.

## 10. Worked example

For the request:

```text
Find me an available Python developer with Django skills under 60 USD per hour.
```

the pipeline behaves as follows:

```mermaid
flowchart LR
    Request[Client request] --> Plan[Profession: Python developer<br/>Preference: relevant Django work]
    Plan --> Constraints[Hard constraints<br/>available<br/>Django<br/>max 60<br/>USD]
    Constraints --> Semantic[Embed complete goal<br/>and rank profiles/projects]
    Semantic --> SQL[SQL verification]
    SQL --> Candidate[Amina Silva<br/>available<br/>USD 40/hour<br/>Python + Django]
    Candidate --> Portfolio[Public project evidence<br/>Django and PostgreSQL work]
    Portfolio --> Review[LLM accepts strong fit]
    Review --> Answer[Candidate + evidence<br/>without repeated questions]
```

The profession and portfolio ideas help retrieval. Availability, Django, rate,
and currency are exact filters because the client explicitly requested them.

If the next message says `give me one with more 60 dollars`, conversation memory
preserves Python, Django, availability, and USD. The constraint normalizer removes
the old maximum and creates `min_hourly_rate = 60`; SQL can then select a record
such as an available USD 80/hour Django developer.

If the request instead says `under 30 USD per hour` and no exact candidate passes,
the search keeps availability, currency, and Django fixed while checking the next
single relaxation. If removing the rate ceiling finds Amina at USD 40/hour, she is
shown only as a **partial near match**, with both the requested ceiling and her
actual rate visible. The stored request itself is not rewritten.

## 11. Failure behavior

```mermaid
flowchart TD
    Failure{Failure type}
    Failure -->|Invalid request| BadRequest[HTTP 400 with validation message]
    Failure -->|Embedding provider unavailable| SearchFailure[No fabricated matches<br/>HTTP 502 or incomplete workflow]
    Failure -->|Planner schema invalid after repair| PlannerFailure[Planning unavailable response]
    Failure -->|Evidence review invalid| ReviewFailure[Stop bounded loop<br/>return incomplete status]
    Failure -->|No database evidence| NoFit[Explain limited sample coverage<br/>ask useful clarifications]
    Failure -->|Repeated retry query| NoProgress[Stop loop to prevent repetition]
```

Provider failures never modify freelancer or project records. A conversation
exchange is saved only after the application has produced an answer.

## 12. Where to change behavior

| Goal | File |
|---|---|
| Change models, ports, timeouts, or retry limit | `src/freelancer_finder/config.py` and `.env` |
| Change route-planning rules or constraint validation | `matching/planner.py` |
| Change vector ranking or SQL filters | `matching/search.py` |
| Change evidence requirements or retry behavior | `matching/review.py` |
| Change tool definitions or agent system prompts | `agent/service.py` |
| Change conversation persistence | `data/memory.py` |
| Change API behavior | `web/server.py` |
| Change the browser experience | `web/static/index.html` |
| Change tables or indexes | `data/schema.sql` |
| Change embedded profile fields | `embeddings/profiles.py` |
