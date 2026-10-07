# Database design

The application uses `data/freelancer.sqlite3` and the schema in
`data/schema.sql`.

## Relationships

```text
freelancers (1) ---- (*) projects
      |
      `------------ (*) freelancer_embeddings

conversations (1) -- (*) conversation_messages
```

`freelancer_id` is retained on every project and embedding row. This is the
stable link used to join vectors back to the complete profile.

## Tables

### `freelancers`

Stores factual profile fields such as name, profession/work field, location,
bio, skills JSON, hourly rate, currency, availability, languages, rating, and
completed-job count.

### `projects`

Stores portfolio title, description, project skills, dates, and `is_public`.
Only public work is supplied to recommendation evidence and project embeddings.

### `freelancer_embeddings`

Stores:

- `freelancer_id`: the profile that owns the vectors.
- `embedding_model`: model required to compare vectors consistently.
- `metadata_json`: includes the profile columns used, freelancer ID, and creation
  time for auditing.
- `contents`: the labeled profile text sent to the embedding provider.
- `embedding_json`: the profile vector.
- `project_contents`: joined public-project text.
- `project_embedding_json`: the separate public-portfolio vector.
- `dimensions` and timestamps for diagnostics.

The search compares a new client-request vector with both stored vectors and
averages the available scores. It then reloads complete candidate rows from SQL
to check exact constraints. Never infer a database fact from a vector value.

### `conversations` and `conversation_messages`

These tables provide local chat memory. A conversation stores an opaque ID and
timestamps; its message rows store only `user` or `assistant` text in sequence.
The agent reads a bounded recent window instead of putting an unlimited chat
transcript into every prompt.

## Inspecting results

From CMD:

```bat
cd /d path\to\freelancer_finder_clean
set PYTHONPATH=%CD%\src
python scripts\inspect_database.py
```

Or inspect concise embedding metadata with SQLite:

```sql
SELECT f.id, f.name, e.embedding_model, e.dimensions,
       length(e.embedding_json) AS profile_vector_characters,
       length(e.project_embedding_json) AS project_vector_characters
FROM freelancer_embeddings AS e
JOIN freelancers AS f ON f.id = e.freelancer_id
ORDER BY f.id;
```
