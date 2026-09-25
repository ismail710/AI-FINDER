# FreelancerEmbedding

| Field | Type | Required | Purpose |
| --- | --- | --- | --- |
| `id` | UUID / string | Yes | Unique embedding ID. |
| `freelancer_id` | UUID / string | Yes | Link to `freelancers.id`. |
| `source_type` | enum | Yes | `profile` or `project`. |
| `source_id` | UUID / string | Yes | Source freelancer or project record ID. |
| `content` | text | Yes | Exact searchable text converted to an embedding. |
| `embedding` | vector / float array | Yes | Numeric vector used in semantic search. |
| `embedding_model` | string | Yes | Model used to create the vector. |
| `dimensions` | integer | Yes | Number of values in the vector. |
| `content_hash` | string | Yes | Detects changes that require regeneration. |
| `created_at` | timestamp | Yes | Vector creation time. |
| `updated_at` | timestamp | Yes | Last regeneration time. |
