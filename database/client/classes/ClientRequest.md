# ClientRequest

| Field | Type | Required | Purpose |
| --- | --- | --- | --- |
| `id` | UUID / string | Yes | Unique request identifier. |
| `client_id` | UUID / string | Yes | Link to `clients.id`. |
| `title` | string | Yes | Short request title. |
| `raw_request` | text | Yes | Client's complete description of the problem to solve. |
| `required_skills` | string array | No | Skills entered by the client before AI analysis. |
| `languages` | string array | No | Required communication or delivery languages. |
| `work_field` | string | No | Relevant field, such as design or marketing. |
| `freelancers_needed` | integer | Yes | Number of freelancers requested. |
| `start_date` | date | No | Desired start date. |
| `deadline` | date | No | Desired completion date. |
| `budget_min` | decimal | No | Optional budget floor. |
| `budget_max` | decimal | No | Optional budget ceiling. |
| `currency` | string | No | Budget currency. |
| `status` | enum | Yes | `draft`, `submitted`, `matching`, `shortlisted`, `staffed`, or `closed`. |
| `created_at` | timestamp | Yes | Request creation time. |
| `updated_at` | timestamp | Yes | Last request update time. |
