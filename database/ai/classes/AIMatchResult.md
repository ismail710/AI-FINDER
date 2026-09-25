# AIMatchResult

| Field | Type | Required | Purpose |
| --- | --- | --- | --- |
| `id` | UUID / string | Yes | Unique result ID. |
| `match_run_id` | UUID / string | Yes | Link to `ai_match_runs.id`. |
| `freelancer_id` | UUID / string | Yes | Link to `freelancers.id`. |
| `rank` | integer | Yes | Position in the recommended shortlist. |
| `proposed_role` | string | No | Suggested role in the solution. |
| `overall_score` | decimal | Yes | Total match score from 0 to 100. |
| `skill_score` | decimal | Yes | Skill-match component. |
| `semantic_score` | decimal | Yes | Profile and portfolio relevance component. |
| `language_score` | decimal | Yes | Language-fit component. |
| `availability_score` | decimal | Yes | Start-date and capacity component. |
| `budget_score` | decimal | Yes | Rate and client-budget component. |
| `match_explanation` | text | Yes | Client-facing reason for the recommendation. |
| `estimated_hours` | decimal | No | Expected effort for this role. |
| `estimated_cost_min` | decimal | No | Low cost estimate. |
| `estimated_cost_max` | decimal | No | High cost estimate. |
| `created_at` | timestamp | Yes | Result creation time. |
