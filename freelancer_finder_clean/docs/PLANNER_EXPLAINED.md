# Understanding `matching/planner.py`

Source: [planner.py](../src/freelancer_finder/matching/planner.py).

`planner.py` turns a client's message and recent conversation into a structured
search plan. It decides whether the request needs freelancer matching, a database
lookup, clarification, or an ordinary conversational response. For matching
requests, it also separates useful search ideas from requirements that must be
obeyed as filters.

The planner does not retrieve candidates or inspect portfolio evidence. It
prepares a validated plan for the other modules to execute.

## The planner's place in the application

```text
User question + recent history + confirmed requirements
    -> LLM proposes a SearchPlan
    -> Pydantic checks the shape and allowed values
    -> Python validates user quotes, filter types, and corrections
    -> service.py routes the plan
        -> matching/review.py runs and reviews a candidate search
        -> SQL agent answers a database question
        -> clarification or conversational reply returns directly
```

The model is allowed to infer professions, helpful skills, and portfolio
examples to improve retrieval. Those inferences do not automatically become
strict database filters. A hard constraint must be tied to wording from the
user, with a few narrowly defined repairs for omissions the code can recover
from that wording.

## 1. Imports and recognition patterns

The module uses:

- `json` to pass prompt context and schemas to the model.
- `math` to reject invalid numeric rates such as infinity or NaN.
- `re` for narrowly defined checks of user wording, including skills, currencies,
  hourly rates, and availability.
- `Literal`, `Any`, and Pydantic's `BaseModel`, `ConfigDict`, and `Field` to define
  and validate planning data.

The compiled regular expressions near the top of the file help with explicit
wording. For example, the skill cues recognize phrases such as “must have
Python,” “required skills,” or “with Django skills.” Broad themes such as
“build an app with AI” do not match those mandatory-skill cues.

These checks are intentionally limited phrase recognizers. They do not
understand every possible paraphrase, so the LLM can still propose a plan, but
the Python checks decide which proposed filters are safe to pass through.

`has_explicit_skill_requirement(text)` is a small public helper that returns
`True` if the skill-requirement expression matches the supplied text. The
semantic tool in `agent/service.py` also uses this helper.

## 2. Strict data models

### `StrictModel`

```python
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
```

All planner models inherit from this class. `extra="forbid"` means Pydantic
rejects unknown fields. If the model invents a key such as `country_filter`,
validation fails rather than silently accepting an unsupported field.

### `ConstraintField`

This `Literal` type restricts filter names to the fields the search system
supports:

```text
availability_status, work_field, min_hourly_rate, max_hourly_rate,
currency, location, required_skills
```

The type rejects other names during Pydantic validation.

### `HardConstraint`

Each hard filter contains:

```json
{
  "field": "location",
  "value": "Portugal",
  "source_quote": "The freelancer must be in Portugal"
}
```

`field` must be a supported `ConstraintField`. `value` can be text, a number, or
a list of skill names. `source_quote` must contain 1 to 1,000 characters. The
model validates the field types and lengths; later Python logic verifies that
the quote actually appears in a user message and that the value is appropriate
for its field.

### `SearchPlan`

`SearchPlan` is the complete output expected from the planning model:

| Field | Meaning |
| --- | --- |
| `route` | One of `match`, `sql`, `clarify`, or `conversation`. |
| `goal` | Short description of what the client wants. Required, 1–800 characters. |
| `professions` | Relevant job types, up to 5. |
| `suggested_skills` | Skills useful for retrieval, up to 8. These are suggestions, not filters by themselves. |
| `portfolio_evidence` | Examples of work that would show relevant experience, up to 5. |
| `criteria_to_confirm` | Important selection criteria that stored data may not verify, up to 5. |
| `hard_constraints` | Explicit, user-sourced filters, up to 6. |
| `removed_constraints` | Previously active fields the user explicitly canceled, up to 6. |
| `search_query` | Focused English description used for semantic retrieval, up to 1,600 characters. |
| `questions` | Up to 3 useful follow-up questions. |
| `reply` | Direct response used for conversation or clarification, up to 800 characters. |

List fields use `default_factory=list`, so a new plan gets its own empty list.
The planner can omit these optional lists and Pydantic supplies empty ones.

The bounds prevent huge model outputs from turning into unbounded prompt or
search data. They also make malformed plans fail early.

## 3. `PLANNER_PROMPT`: instructions sent to the LLM

`PLANNER_PROMPT` tells the model how to reason before it returns a `SearchPlan`.
The instructions cover several important rules:

- Understand the client's desired outcome before choosing a profession.
- Infer likely roles and useful search terms without turning those suggestions
  into mandatory filters.
- Use `match` for a clear project goal even when the client did not explicitly
  say “hire.”
- Use `sql` for factual counts and lookups of named stored records.
- Use `clarify` only when the goal is too unclear for a meaningful profession.
- Use `conversation` for greetings and general discussion without a task.
- Do not assume country, language, currency, remote work, or local licensing.
- Attach exact user wording to every hard constraint in `source_quote`.
- Preserve previously confirmed requirements unless a newer user message changes
  or cancels them.
- Keep a total project budget separate from an hourly rate.
- Ask questions about important criteria the database cannot verify.
- Return only one JSON object matching the schema.

The prompt influences model behavior. The following Python validation provides
additional checks before the plan is sent to search.

## 4. Small text helpers

### `message_text(content)`

Converts a model response into a string. If `content` is already a string, it is
returned directly. If it is a list, text fields from dictionary items are
joined with newlines and other items are converted to strings. Other values are
converted with `str()`.

### `normalized(value)`

Lowercases text with `casefold()` and collapses runs of whitespace. This allows
the provenance check to treat capitalization or extra spaces as equivalent.
It does not ignore punctuation or paraphrases: the quoted wording still needs to
appear as a substring of a user message.

## 5. Carrying and checking hard requirements

### `merge_confirmed_constraints(plan, confirmed_constraints)`

Conversation memory can supply requirements that the original message history
no longer contains. This function carries them into the new plan:

1. Start with previously confirmed constraints, except fields listed in
   `removed_constraints`.
2. Add the plan's current constraints. If one uses the same field, it replaces
   the saved one.
3. Store the merged constraints back on the plan.

For example, a saved location requirement remains active when a client asks “Can
you find another person?” If the latest plan places `location` in
`removed_constraints`, that saved location is omitted.

### `constraint_arguments(plan, user_messages)`

This is the main gate between the LLM's proposed hard filters and the search
code. It returns a dictionary of validated filter arguments, such as:

```python
{
    "location": "Portugal",
    "max_hourly_rate": 40.0,
    "currency": "EUR",
}
```

For each constraint, it checks:

1. **Provenance:** normalized `source_quote` text must be present in at least one
   user message. A quote made up by the model, or copied from an assistant reply,
   raises `ValueError`.
2. **Uniqueness:** the same field cannot appear twice in the plan.
3. **Field-specific type and value:**
   - `required_skills` must be a nonempty list of nonempty strings, and its quote
     must contain explicit mandatory skill wording.
   - Hourly rate bounds must be finite, nonnegative numbers. A total budget alone
     cannot pass as an hourly rate. A short correction can use earlier hourly
     context when it includes a minimum or maximum comparison phrase.
   - Other filters must be nonempty text.
   - Availability must be `available`, `partial`, or `unavailable`.
   - Currency must be a three-letter alphabetic code such as `EUR`.
4. **Paired rate and currency:** a rate bound requires a currency, and a currency
   requires a rate bound.
5. **Valid range:** if both minimum and maximum rates exist, the minimum cannot
   exceed the maximum.

The function raises an error when checks fail. In `create_search_plan()`, that
error causes one schema-repair attempt. If the repaired result is still invalid,
planning fails rather than passing an unchecked filter to search.

This is a provenance check, not a full natural-language proof. It checks that
the model's quote text occurs in a user message and then applies field-specific
guards. The regular expressions cover common wordings rather than every possible
way of expressing a requirement.

## 6. Deterministic repairs from user wording

The following helpers compensate for specific omissions by a small LLM. They
read user wording or already verified plan fields; they do not derive strict
filters from a general project theme.

### `_currency_from_text(text)`

Recognizes clear USD, EUR, and GBP wording (including names and symbols). If no
supported currency is stated, it returns `None`; it does not guess from the
country or language.

### `apply_latest_rate_correction(plan, user_messages)`

Looks at the newest user message for common minimum phrases such as “over 60” or
“at least 60,” and maximum phrases such as “under 60” or “up to 60.” It also
requires rate-related context, such as “hourly,” “per hour,” “euros,” or a
currency symbol.

When it finds a correction, it removes the previous minimum, maximum, and
currency constraints, then adds the newest bound. It can carry forward a
previous currency when the conversation established it. It also updates the
plan's `goal` and `search_query` suffix so the retrieval description reflects
the new bound.

Example:

```text
Earlier: “under 80 EUR per hour”
Latest:  “actually, over 60 per hour”
Result:  minimum rate 60, with the established EUR currency
```

### `_AVAILABILITY_CUES` and `apply_latest_availability(...)`

`_AVAILABILITY_CUES` maps common phrases to the database's three availability
values. The helper scans user messages from newest to oldest. When it finds an
explicit availability phrase, it replaces the current availability constraint
with one containing that phrase as its source quote.

The order of the cue patterns checks `unavailable` before `available`, so the
word “unavailable” is not mistaken for “available.”

### `remove_unknown_work_field(plan, catalog)`

The catalog contains exact work-field names present in the stored database. If
the plan contains a `work_field` filter that does not match one of those names,
this helper drops that filter. The profession can still remain in
`professions` and `search_query` as a semantic preference.

This avoids an exact database category filter that would exclude every record
simply because the user's job title differs from the database's category labels.
It does not prevent semantic search from trying that profession.

### `complete_explicit_hourly_currency(plan)`

Sometimes the LLM extracts a rate from wording like “under 60 USD per hour” but
omits the separate `currency` field. This helper reads a three-letter currency
code directly from the rate constraint's quote and adds the missing field.
Currency symbols alone do not qualify for this repair, since the symbol may be
ambiguous.

### `complete_explicit_skill_constraints(plan, user_messages)`

If the plan has no `required_skills` constraint, the helper searches the user
messages from newest to oldest for wording like “with Python and Django skills.”
It takes the skill names from that sentence, removes a few leading strength
descriptors, splits the names on commas, slashes, or “and,” and adds them as a
required-skill constraint with the matching user phrase as its quote.

If the plan already has any `required_skills` constraint, the helper leaves it
unchanged. The names come from user wording; “build a booking app” by itself
does not trigger this helper.

### `remove_satisfied_followups(plan, constraints)`

Once a constraint has been checked as a database filter, the planner should not
ask the client to confirm the same point again. This helper builds simple text
markers from the checked filters and removes `criteria_to_confirm` items and
questions containing those markers.

For example, when `location="Portugal"` is a verified filter, a follow-up
asking “What location do you prefer?” is removed. This is a text-marker check,
so it is intentionally simple rather than a full semantic comparison.

## 7. Structured model output and one repair attempt

### `structured_response(model, prompt, context, schema, validate=None)`

This helper asks the model for a response in a specific Pydantic schema:

1. It adds the JSON schema generated from `schema` to the system prompt.
2. It serializes the context as JSON for the user message.
3. When the provider supports the relevant interface, it also passes a native
   JSON-schema output option for Ollama or OpenAI-compatible models.
4. It extracts the response text, strips a surrounding Markdown JSON fence if
   present, and validates the result with `schema.model_validate_json(...)`.
5. If both Pydantic validation and the optional custom `validate` function pass,
   it returns the typed model instance.
6. If parsing or validation fails, it sends the error and the invalid response
   back for one correction attempt.
7. If the second response is invalid, it raises
   `ValueError("The model did not return a valid structured decision")`.

The loop uses `range(2)`: the original call plus at most one repair call. It does
not invoke search tools while it repairs the planner's JSON. Per-call token
options are omitted because the application sets each model role's output limit
when constructing its model client.

The native structured-output option is selected by inspecting the model class's
module name. Other providers still receive the schema in the prompt and are
validated by Pydantic after generation.

## 8. Main entry point: `create_search_plan(...)`

This function coordinates the planner. Its parameters are:

- `model`: the configured planning chat model.
- `question`: the newest user request.
- `history`: recent user and assistant turns.
- `catalog`: database coverage metadata from the search layer.
- `confirmed_constraints`: previously validated requirements loaded from
  conversation memory, if available.

First it combines confirmed source quotes, previous user turns, and the current
question into `user_messages`. That complete list supports provenance checks
and ensures deterministic correction helpers can use the latest wording.

Then it defines a validation callback that runs after Pydantic parses each
candidate plan. In order, that callback:

1. Merges saved constraints unless the user removed or replaced them.
2. Applies an explicit hourly-rate correction in the latest wording.
3. Applies the latest explicit availability requirement.
4. Recovers a narrowly phrased mandatory skill requirement if omitted.
5. Recovers an explicit three-letter currency code if the rate quote includes it.
6. Drops an unknown exact work-field category.
7. Calls `constraint_arguments()` to validate provenance and filter values.
8. Removes follow-up questions that repeat already checked constraints.
9. Requires matching plans to include both a search query and at least one
   profession.

Finally it passes the prompt, context, `SearchPlan` schema, and validation
callback to `structured_response()`.

The model receives the current question, at most the last 10 history turns, the
active confirmed constraints, and a small database summary. The category labels
are intentionally withheld from the planner: the prompt should infer the
profession from the client's goal rather than be anchored to whatever categories
happen to exist in a small sample database. Candidate retrieval and evidence
review happen later.

The function returns a validated `SearchPlan`. Downstream code can then use
`constraint_arguments()` to obtain the search filters and `search_query` to
retrieve semantically relevant records.

## 9. Worked example

Suppose the history contains:

```text
User: I need someone in Portugal under 80 EUR per hour.
Assistant: I can look for a suitable professional.
User: Actually, show me people over 60 per hour with Django skills.
```

The planner's intended behavior is:

1. Infer the relevant profession from the project goal and put useful search
   language into `search_query`.
2. Preserve Portugal because it was an explicit earlier requirement.
3. Replace the old maximum rate with a minimum of 60, carrying forward EUR from
   the earlier hourly request.
4. Add Django as required because the latest message says “with Django skills.”
5. Keep other inferred skills as retrieval suggestions rather than hard filters.
6. Validate that each strict field has user wording as its source.
7. Return the plan for matching and evidence review.

The exact route and extra search terms depend on the LLM's understanding of the
project goal. The provenance, rate, availability, and other Python checks still
apply to the resulting plan.

## 10. Errors and practical limits

Planning can raise an error when:

- The model returns invalid JSON or a field outside the schema, even after its
  single repair attempt.
- A quote is not found in the user messages.
- A filter has the wrong type, an unsupported value, duplicate fields, or an
  invalid rate/currency combination.
- A matching route lacks a usable search query or profession.

The calling layer in `agent/service.py` catches planner errors and returns a
planning-unavailable response. It does not silently continue with invalid hard
filters.

Some decisions use regular expressions and substring matching. They are
transparent and easy to test, but they will not recognize every natural-language
paraphrase. If a requirement is ambiguous, a clarification is safer than
inventing a strict filter.

For related code, see [service.py explained](SERVICE_EXPLAINED.md), the
[matching walkthrough](CODE_WALKTHROUGH.md), and the implementation files
[`search.py`](../src/freelancer_finder/matching/search.py) and
[`review.py`](../src/freelancer_finder/matching/review.py).
