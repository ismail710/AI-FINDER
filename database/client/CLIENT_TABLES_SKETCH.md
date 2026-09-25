# AI Freelancer Matcher — Client Data Sketch

This table stores the person or company asking for freelance help. Project requirements such as needed skills, budget, and deadline belong in a future `client_requests` table, not directly on the client profile.

## `clients`

| Field | Type | Required | Why it is needed |
| --- | --- | --- | --- |
| `id` | UUID / string | Yes | Unique client identifier. |
| `name` | string | Yes | Primary contact's name. |
| `email` | string | Yes | Unique contact and login email. |
| `phone` | string | No | Optional contact number. |
| `photo` | URL / string | No | Profile photo or company logo. |
| `company_name` | string | No | Client's company or organisation. |
| `job_title` | string | No | Contact's role, such as founder or product manager. |
| `company_website` | URL / string | No | Company website. |
| `industry` | string | No | Business sector, for example retail or finance. |
| `company_size` | enum | No | `solo`, `small`, `medium`, or `enterprise`. |
| `location` | string | No | City or country. |
| `timezone` | string | No | Helps arrange calls and collaboration. |
| `languages` | string array | Yes | Preferred languages for communication. |
| `bio` | text | No | Short description of the client or company. |
| `is_verified` | boolean | Yes | Whether the platform verified the account. |
| `created_at` | timestamp | Yes | Account creation time. |
| `updated_at` | timestamp | Yes | Last profile update time. |

### Example

```json
{
  "id": "client_001",
  "name": "Noah Martin",
  "email": "noah@catalyststudio.com",
  "phone": "+351 912 000 111",
  "company_name": "Catalyst Studio",
  "job_title": "Founder",
  "company_website": "https://catalyststudio.example",
  "industry": "Hospitality",
  "company_size": "small",
  "location": "Lisbon, Portugal",
  "timezone": "Europe/Lisbon",
  "languages": ["English", "Portuguese"],
  "bio": "Independent hospitality group looking for digital product support.",
  "is_verified": false
}
```

## `client_requests`

| Field | Type | Required | Why it is needed |
| --- | --- | --- | --- |
| `id` | UUID / string | Yes | Unique request identifier. |
| `client_id` | UUID / string | Yes | Links the request to `clients.id`. |
| `title` | string | Yes | Short request title. |
| `raw_request` | text | Yes | Complete problem description sent to the AI analyser. |
| `required_skills` | string array | No | Skills entered by the client. |
| `languages` | string array | No | Required communication or delivery languages. |
| `work_field` | string | No | Relevant field, such as design or software. |
| `freelancers_needed` | integer | Yes | Number of people requested. |
| `start_date` | date | No | Desired project start date. |
| `deadline` | date | No | Desired completion date. |
| `budget_min` | decimal | No | Optional budget floor. |
| `budget_max` | decimal | No | Optional budget ceiling. |
| `currency` | string | No | Budget currency. |
| `status` | enum | Yes | `draft`, `submitted`, `matching`, `shortlisted`, `staffed`, or `closed`. |
| `created_at` | timestamp | Yes | Request creation time. |
| `updated_at` | timestamp | Yes | Last request update time. |

```text
clients 1 ─── * client_requests
```
