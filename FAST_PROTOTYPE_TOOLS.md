# Fast Prototype Tools - Firebase Option

## Recommendation

Use **Firebase** instead of Supabase for the first working prototype. It provides the database, authentication, server-side functions, file storage, and real-time updates in one managed platform, so the team can focus on matching quality rather than backend setup.

For the first version, avoid complex vector-search infrastructure. With a controlled dataset of 20-50 freelancers, a Firebase function can load eligible profiles and use a simple score based on skills, language, availability, rate, and response history. Add vector search only after the core workflow works well.

## Tool stack

| Area | Tool | Use in the prototype |
| --- | --- | --- |
| Web application | Next.js + React | Client request form, shortlist, freelancer profile, and response dashboard. |
| Styling | Tailwind CSS | Fast responsive UI development. |
| Database | Cloud Firestore | Store freelancer profiles, client requests, matches, invitations, availability, and responses. |
| Authentication | Firebase Authentication | Sign in clients, freelancers, and administrators. |
| Backend and matching logic | Cloud Functions for Firebase (TypeScript) | Securely call the AI, calculate rankings and budget estimates, and send invitations. |
| AI analysis | Hugging Face Inference Providers | Extract structured requirements from client free-text requests and create match explanations with an open model. |
| File storage | Firebase Cloud Storage | Store freelancer CVs, portfolio images, and supporting documents. |
| Email invitations | Resend | Send an invitation to each recommended freelancer with Accept, Decline, or Question actions. |
| Real-time updates | Firestore listeners | Show the client immediately when a freelancer views, accepts, declines, or messages about an invitation. |
| Deployment | Firebase App Hosting or Vercel | Deploy the web application. Use Firebase App Hosting when keeping the whole prototype in Firebase; use Vercel if the team already prefers it for Next.js. |
| Local testing | Firebase Local Emulator Suite | Test Firestore, Authentication, and Cloud Functions locally before deployment. |

## Simple matching method for version 1

Each freelancer receives a score out of 100:

| Factor | Example weighting | Rule |
| --- | ---: | --- |
| Required expertise | 35 points | Award points for each mandatory skill matched. |
| Relevant work field | 15 points | Award points when the freelancer's field or portfolio matches the project. |
| Language match | 10 points | Award points for every required communication or delivery language. |
| Availability | 20 points | Give the highest score to freelancers who can start within the requested timeframe. |
| Budget fit | 10 points | Favor rates that fit the client budget or calculated estimate. |
| Response history | 10 points | Favor freelancers with a reliable, timely response rate. |

Remove freelancers who do not meet non-negotiable requirements, such as a required language, unavailable start date, or budget ceiling. Show the top 3-5 remaining profiles with an explanation of their score.

## Fast prototype flow

1. An administrator imports 20-50 freelancer profiles into Firestore.
2. A freelancer can sign in and update availability, available start date, weekly capacity, and rate.
3. A client submits a description of their problem, skills needed, deadline, team size, and budget.
4. A Cloud Function sends the description to a Hugging Face Inference Provider and saves structured requirements.
5. The same function filters and scores eligible freelancers from Firestore.
6. The client receives a ranked shortlist, a recommended solution or team, and an estimated price range.
7. The client sends invitations to selected freelancers.
8. Resend emails the invitations, and the freelancer responds through a secure link or dashboard.
9. Firestore updates the client dashboard in real time with each response.

## Firestore collections

```text
freelancers/{freelancerId}
  profile, skills, languages, workFields, rate, availabilityStatus,
  availableFrom, weeklyCapacity, portfolioSummary, responseMetrics

clientRequests/{requestId}
  clientId, rawRequest, structuredRequirements, teamSize, timeline,
  budgetMin, budgetMax, status

matches/{matchId}
  requestId, freelancerId, score, scoreBreakdown, matchExplanation,
  proposedRole, estimatedCost

invitations/{invitationId}
  matchId, sentAt, viewedAt, responseStatus, respondedAt, responseMessage
```

## Functions to build first

- `analyseClientRequest`: turns the client's description into structured requirements.
- `findMatches`: filters freelancers, calculates score, and saves the shortlist.
- `estimateBudget`: calculates low and high price estimates for the recommended team.
- `sendInvitation`: sends an email and creates an invitation record.
- `recordInvitationResponse`: accepts a freelancer action and updates the client view.
- `updateAvailability`: allows a freelancer to change capacity and possible start date.

## Build order

1. Create Firebase project, Authentication, and Firestore collections.
2. Add a small set of realistic freelancer records manually.
3. Build the client request form and display stored requests.
4. Implement `analyseClientRequest` and `findMatches`.
5. Display the shortlist, rationale, availability, and budget estimate.
6. Add invitations and response tracking.
7. Test with realistic urgent and non-urgent client requests.

## Why this is faster

- One managed setup covers data, sign-in, backend logic, storage, and live UI updates.
- The prototype can use an understandable score model before investing in advanced retrieval.
- Firebase's local emulator supports testing the main backend services before deployment.
- The architecture can grow later: Firestore supports vector indexes if semantic retrieval becomes necessary at larger scale.

## Important prototype rule

Always show availability and response status next to every recommendation. A technically strong freelancer is not a useful match if they cannot start on time or do not respond when the client needs an answer.
