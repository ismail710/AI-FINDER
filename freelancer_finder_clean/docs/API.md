# HTTP API

Start the server with `run.cmd --port 8780`. All POST bodies are JSON and all
responses are JSON.

## Health and configuration

```bat
curl http://127.0.0.1:8780/api/status
```

The response identifies the selected chat model, embedding model, database file,
and sample row counts. It never returns provider tokens.

## Chat (recommended)

```bat
curl -X POST http://127.0.0.1:8780/api/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"I need an available Python developer for an analytics dashboard\",\"conversation_id\":\"demo-thread-1234\"}"
```

The response includes:

- `answer`: text shown to the client.
- `conversation_id`: opaque ID used to load the same memory on the next turn.
- `source`: the selected route/workflow.
- `attempts`: number of evidence-review attempts.
- `plan`: inferred professions, suggested skills, portfolio evidence, criteria,
  validated constraints, and follow-up questions.
- `matches`: candidate cards backed by SQLite data.

For a follow-up, send the same `conversation_id`; the server loads recent history
from SQLite. The older `history` array is accepted only for compatibility when a
caller has not supplied a conversation ID.

## Restore conversation messages

```bat
curl http://127.0.0.1:8780/api/conversations/demo-thread-1234/messages
```

This returns up to 50 stored user/assistant messages in chronological order. It
is intended for the local UI. A production API must authenticate access to each
conversation rather than relying on possession of a random ID alone.

## Direct semantic match

```bat
curl -X POST http://127.0.0.1:8780/api/match ^
  -H "Content-Type: application/json" ^
  -d "{\"query\":\"restaurant brand identity and menu design\",\"top\":3}"
```

Optional exact filters are `availability_status`, `work_field`,
`min_hourly_rate`, `max_hourly_rate`, `currency`, `location`, and
`required_skills`. Use filters only when the client explicitly requires them.
A total project budget is not an hourly-rate filter.

The direct `/api/match` endpoint applies these filters exactly. The conversational
matching workflow first applies them exactly and, only if zero records pass, may
return a controlled near match after relaxing one condition. Such a response has
`verification_status: "near_matches"`, includes `constraint_notes`, and records
the original, applied, and relaxed constraints in its search metadata.

## SQL-backed question

```bat
curl -X POST http://127.0.0.1:8780/api/sql ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"How many available freelancers are stored?\"}"
```

This route exposes only read-only SQL tools to the LLM. It is intended for
counts, named profile details, and comparisons—not recommendations.

## Errors

Validation failures use HTTP 400. Unexpected provider or server failures use
HTTP 500 and return a short `error` string. Check the server CMD window for the
full stack trace. A provider error does not modify the SQLite database.
