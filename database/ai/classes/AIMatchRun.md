# AIMatchRun

| Field | Type | Required | Purpose |
| --- | --- | --- | --- |
| `id` | UUID / string | Yes | Unique matching-run ID. |
| `client_request_id` | UUID / string | Yes | Future link to `client_requests.id`. |
| `analysis_id` | UUID / string | Yes | Link to `ai_request_analyses.id`. |
| `status` | enum | Yes | `pending`, `running`, `completed`, or `failed`. |
| `retrieval_method` | string | Yes | For example `filters+vector` or `keyword`. |
| `candidate_count` | integer | Yes | Number of eligible profiles considered. |
| `model_name` | string | No | AI model used for explanations or reranking. |
| `started_at` | timestamp | Yes | Start time. |
| `completed_at` | timestamp | No | Completion time. |
| `error_message` | text | No | Failure details for debugging. |
