# AI Freelancer Matcher — Data Sketch

The first version has two connected tables: `freelancers` and `projects`. Your original fields are included; the added fields support AI retrieval, practical matching, and reliable portfolio data.

## `freelancers`

| Field | Type | Required | Why it is needed |
| --- | --- | --- | --- |
| `id` | UUID / string | Yes | Unique freelancer identifier. |
| `name` | string | Yes | Freelancer name. |
| `email` | string | Yes | Unique contact and login email. |
| `age` | integer | Yes | Basic profile information. |
| `bio` | text | Yes | Short searchable professional introduction. |
| `portfolio` | URL / string | No | Portfolio, LinkedIn, or GitHub link. |
| `photo` | URL / string | No | Profile photo. |
| `interests` | string array | No | Topics and work areas the freelancer enjoys. |
| `languages` | string array | Yes | Languages spoken or used professionally. |
| `skills` | string array | Yes | Expertise for matching a client request. |
| `work_field` | string | Yes | Main service field: design, software, marketing, etc. |
| `experience_years` | integer | No | Years of relevant experience. |
| `location` | string | No | City or country, when work must be local. |
| `timezone` | string | No | Helps assess collaboration overlap. |
| `hourly_rate` | decimal | No | Used for the expected price range. |
| `currency` | string | No | Currency for the hourly rate. |
| `availability_status` | enum | Yes | `available`, `partial`, or `unavailable`. |
| `available_from` | date | No | Earliest date the freelancer can start. |
| `weekly_capacity_hours` | integer | No | Hours available each week. |
| `projects` | project ID array | No | IDs of the freelancer's project records. |
| `is_verified` | boolean | Yes | Shows whether the platform checked the profile. |
| `created_at` | timestamp | Yes | When the profile was created. |
| `updated_at` | timestamp | Yes | When the profile was last updated. |

### Example

```json
{
  "id": "freelancer_001",
  "name": "Amina Silva",
  "email": "amina@example.com",
  "age": 29,
  "bio": "Frontend developer building accessible SaaS products.",
  "portfolio": "https://amina.dev",
  "interests": ["AI", "web design", "startups"],
  "languages": ["English", "Portuguese"],
  "skills": ["React", "TypeScript", "Next.js"],
  "work_field": "Software development",
  "experience_years": 6,
  "hourly_rate": 65,
  "currency": "EUR",
  "availability_status": "available",
  "available_from": "2026-10-01",
  "weekly_capacity_hours": 25,
  "projects": ["project_001"],
  "is_verified": false
}
```

## `projects`

| Field | Type | Required | Why it is needed |
| --- | --- | --- | --- |
| `id` | UUID / string | Yes | Unique project identifier. |
| `freelancer_id` | UUID / string | Yes | Connects the project to its freelancer. |
| `title` | string | Yes | Project name. |
| `detail` | text | Yes | What was built, the freelancer's contribution, and outcome. |
| `photos` | URL array | No | Project or portfolio image URLs. |
| `project_url` | URL / string | No | Link to the live project or full case study. |
| `work_field` | string | Yes | Field demonstrated by the project. |
| `skills_used` | string array | Yes | Technologies and skills demonstrated. |
| `role` | string | No | Freelancer's role, for example UX designer or full-stack developer. |
| `client_industry` | string | No | Industry served, such as hospitality or finance. |
| `completed_at` | date | No | Completion date. |
| `is_public` | boolean | Yes | Whether clients may view the project. |
| `created_at` | timestamp | Yes | When the project record was created. |

### Example

```json
{
  "id": "project_001",
  "freelancer_id": "freelancer_001",
  "title": "Restaurant booking website",
  "detail": "Designed and built an online booking system that reduced telephone reservations.",
  "photos": [
    "https://images.example.com/restaurant-home.jpg",
    "https://images.example.com/restaurant-booking.jpg"
  ],
  "project_url": "https://project.example.com",
  "work_field": "Software development",
  "skills_used": ["Next.js", "Stripe", "PostgreSQL"],
  "role": "Full-stack developer",
  "client_industry": "Hospitality",
  "is_public": true
}
```

## Relationship

```text
freelancers 1 ─── * projects
```

One freelancer can have many projects. Store the reliable database link in `projects.freelancer_id`; `freelancers.projects` is a convenient list for displaying the portfolio on a profile page.
