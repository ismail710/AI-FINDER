# AI Freelancer Matching Platform - Prototype Tools

## Prototype goal

Build a working prototype that receives a client request, retrieves suitable freelancer profiles, checks availability, recommends an individual or team, estimates a budget range, and tracks freelancer responses.

## Local-first setup

The prototype can run entirely on one computer:

- **Node.js** runs the web application.
- **SQLite** is a single local file, for example `data/freelancers.db`; no database server is required.
- **Ollama** runs the language model and embeddings locally after its models have been downloaded.
- **Next.js** runs locally at `http://localhost:3000` during development.

For the fastest first version, begin with regular SQLite filtering and keyword matching. Add the SQLite vector extension only after basic matching works, to improve semantic search for longer client requests.

## Recommended tools

| Area | Tool | Purpose in the prototype |
| --- | --- | --- |
| User interface | Next.js + React | Build the client request form, recommendation screen, and simple freelancer dashboard. |
| Styling | Tailwind CSS | Create a fast, responsive, consistent interface. |
| Local database | SQLite | Store freelancer profiles, skills, languages, rates, availability, client requests, matches, and invitation responses in one local database file. |
| Database access | Drizzle ORM | Define the database schema in TypeScript and make local queries simple and type-safe. |
| Authentication | Simple prototype login | Use a small local role selector or password-protected test accounts for client, freelancer, and administrator views. Add production authentication later. |
| Data collection | Local admin dashboard | Add and update freelancer profiles, portfolios, rates, work fields, and availability in the prototype. |
| AI request analysis | Ollama | Run an AI model locally to convert a client's free-text problem into structured needs: skills, languages, work field, roles, team size, timeline, and budget signals. |
| Semantic matching | Ollama embeddings + SQLite vector extension | Find freelancers whose profile, experience, and portfolio are relevant to the client's problem, not only exact keyword matches. |
| Rule-based filtering | SQLite queries | Filter results by required language, hourly or fixed rate, availability, location if required, and team capacity. |
| Recommendation logic | Server-side TypeScript service | Combine semantic match score, required criteria, availability, price, and responsiveness into a ranked shortlist. |
| Budget estimation | Server-side TypeScript service | Calculate a price range using freelancer rates, expected hours or duration, number of roles, and a clear set of assumptions. |
| Availability management | SQLite database + local dashboard | Let freelancers mark their status as available, partially available, or unavailable, with a possible start date and weekly capacity. |
| Immediate response | In-app invitation screen | Let a freelancer accept, decline, or ask a question from the local prototype. Email can be added after matching is validated. |
| Response tracking | SQLite database + API routes | Record when a freelancer was notified, viewed the request, responded, and accepted or declined. |
| Notifications | In-app notifications; optional SMTP email later | Show response updates in the prototype without requiring a third-party email service. |
| Local runtime | Next.js local server | Run the application on the developer's computer with `npm run dev`. |
| Monitoring | Browser console + application logs | Inspect errors, failed requests, and AI or database performance during testing. |

## Minimum working prototype flow

1. An administrator adds at least 20-50 realistic freelancer profiles.
2. Each profile includes expertise, languages, work field, rate, portfolio summary, availability, start date, and response status.
3. A client submits a request describing the problem, required skills, language, deadline, number of freelancers, and budget if known.
4. Ollama extracts structured requirements from the request on the local computer.
5. The application filters out freelancers who do not meet mandatory requirements or are unavailable.
6. Embeddings and matching rules rank the remaining freelancers.
7. The client sees a shortlist, matching explanation, proposed team or solution, and estimated budget range.
8. The client sends an in-app invitation to one or more freelancers.
9. The system records each freelancer response in the local database.
10. The client sees responses and can choose a freelancer or team.

## Suggested core database records

- `freelancers`: name, profile summary, hourly rate, work field, availability status, available start date, weekly capacity, response-time target.
- `freelancer_skills`: freelancer ID, skill, proficiency, years of experience.
- `freelancer_languages`: freelancer ID, language, proficiency.
- `portfolio_items`: freelancer ID, project summary, industry, technologies, project outcome.
- `client_requests`: client ID, original request, structured requirements, timeline, requested team size, budget.
- `matches`: request ID, freelancer ID, match score, match explanation, proposed role, estimated cost.
- `invitations`: match ID, sent time, viewed time, response status, response time, freelancer message.

## AI prompt outputs

The AI should return structured JSON for each request:

```json
{
  "problem_summary": "",
  "required_skills": [],
  "preferred_skills": [],
  "languages": [],
  "field_of_work": "",
  "roles_needed": [],
  "freelancers_needed": 1,
  "start_date": "",
  "deadline": "",
  "availability_urgency": "standard",
  "budget_min": null,
  "budget_max": null,
  "clarifying_questions": []
}
```

## First version scope

Use a controlled freelancer dataset, SQLite, Ollama, and in-app invitations. This makes the prototype quick to run locally and avoids cloud service setup. Do not begin with automated web scraping, contracts, payments, or a public marketplace. The important proof is that the application produces relevant, available, responsive freelancer recommendations with a useful budget estimate.

## Later additions

- Calendar integration for live availability.
- Email, WhatsApp, or SMS notifications for urgent requests.
- Freelancer self-service profile updates.
- Client feedback and completed-project ratings to improve ranking.
- Contracts, milestones, invoices, and payments.
- Analytics for supply, demand, placement rate, and skill gaps.
