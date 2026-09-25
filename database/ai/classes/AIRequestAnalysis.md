# AIRequestAnalysis

| Field | Type | Required | Purpose |
| --- | --- | --- | --- |
| `id` | UUID / string | Yes | Unique analysis ID. |
| `client_request_id` | UUID / string | Yes | Future link to `client_requests.id`. |
| `raw_request` | text | Yes | Original request text analysed by AI. |
| `problem_summary` | text | Yes | Concise AI-generated explanation of the problem. |
| `required_skills` | string array | Yes | Mandatory skills extracted from the request. |
| `preferred_skills` | string array | No | Useful but optional skills. |
| `languages` | string array | No | Communication or delivery languages required. |
| `work_field` | string | No | Relevant work field. |
| `roles_needed` | string array | No | Roles needed for a team solution. |
| `freelancers_needed` | integer | Yes | Requested number of freelancers. |
| `start_date` | date | No | Desired project start. |
| `deadline` | date | No | Desired completion date. |
| `budget_min` | decimal | No | Budget floor extracted or entered by client. |
| `budget_max` | decimal | No | Budget ceiling extracted or entered by client. |
| `clarifying_questions` | string array | No | Questions needed before a confident match. |
| `model_name` | string | Yes | AI model that produced the analysis. |
| `prompt_version` | string | Yes | Version of the analysis instruction. |
| `created_at` | timestamp | Yes | Analysis time. |
