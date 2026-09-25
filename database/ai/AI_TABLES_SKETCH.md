# AI Freelancer Matcher — AI Data Sketch

This module stores the AI work behind freelancer retrieval and matching. It does not replace the main `freelancers` or future `client_requests` tables; it records their AI analysis, embeddings, match runs, and explainable results.

## Tables

| Table / class | Purpose |
| --- | --- |
| `ai_request_analyses` | Converts a client request into structured requirements. |
| `freelancer_embeddings` | Stores searchable vector representations of a freelancer profile or project. |
| `ai_match_runs` | Records one complete attempt to find matches for a request. |
| `ai_match_results` | Saves every candidate result, score breakdown, explanation, and cost estimate. |

## External relationships

```text
freelancers 1 ─── * freelancer_embeddings
freelancers 1 ─── * ai_match_results
client_requests 1 ─── * ai_request_analyses
client_requests 1 ─── * ai_match_runs
ai_request_analyses 1 ─── * ai_match_runs
ai_match_runs 1 ─── * ai_match_results
```

`client_requests` is the next core table to create in the Client module. Until it exists, its IDs can be treated as planned references.

## Folder structure

| Location | Contents |
| --- | --- |
| `classes/AIRequestAnalysis.md` | Request analysis entity. |
| `classes/FreelancerEmbedding.md` | Vector-search entity. |
| `classes/AIMatchRun.md` | Matching job entity. |
| `classes/AIMatchResult.md` | Ranked recommendation entity. |
| `AI_ER_DIAGRAM.drawio` | Editable complete AI data diagram. |
