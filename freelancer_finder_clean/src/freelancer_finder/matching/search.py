"""Rank freelancers for a client request using saved profile and project vectors.

Run from the clean project root with ``PYTHONPATH=src``:
    python -m freelancer_finder.matching.search "I need a Python Django developer"
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from huggingface_hub import InferenceClient

from ..config import DEFAULT_DATABASE_PATH, settings
from ..data.database import database_session


EMBEDDING_MODEL = settings.embedding_model


def cosine_similarity(first: list[float], second: list[float]) -> float:
    """Compare two vectors; return a value from -1 to 1."""
    if len(first) != len(second) or not first:
        raise ValueError("Embedding vectors must be nonempty and have equal dimensions.")
    dot_product = math.fsum(a * b for a, b in zip(first, second))
    first_norm = math.sqrt(math.fsum(value * value for value in first))
    second_norm = math.sqrt(math.fsum(value * value for value in second))
    if first_norm == 0 or second_norm == 0:
        raise ValueError("Cannot compare a zero-length embedding vector.")
    return dot_product / (first_norm * second_norm)


def match_freelancers(
    prompt: str,
    *,
    top: int | None = 5,
    availability_status: str | None = None,
    work_field: str | None = None,
    min_hourly_rate: float | None = None,
    max_hourly_rate: float | None = None,
    currency: str | None = None,
    location: str | None = None,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> list[dict[str, object]]:
    """Apply optional SQL filters, then rank freelancers by saved vectors."""
    if not prompt.strip():
        raise ValueError("The client request cannot be empty.")
    if top is not None and top < 1:
        raise ValueError("top must be at least 1.")
    if availability_status not in {None, "available", "partial", "unavailable"}:
        raise ValueError("availability_status must be available, partial, or unavailable.")
    if min_hourly_rate is not None and min_hourly_rate < 0:
        raise ValueError("min_hourly_rate cannot be negative.")
    if max_hourly_rate is not None and max_hourly_rate < 0:
        raise ValueError("max_hourly_rate cannot be negative.")
    if min_hourly_rate is not None and max_hourly_rate is not None and min_hourly_rate > max_hourly_rate:
        raise ValueError("min_hourly_rate cannot exceed max_hourly_rate.")

    conditions = ["e.embedding_model = ?"]
    sql_parameters: list[object] = [EMBEDDING_MODEL]
    if availability_status:
        conditions.append("f.availability_status = ?")
        sql_parameters.append(availability_status)
    if work_field:
        conditions.append("f.work_field = ? COLLATE NOCASE")
        sql_parameters.append(work_field)
    if min_hourly_rate is not None:
        conditions.append("f.hourly_rate > ?")
        sql_parameters.append(min_hourly_rate)
    if max_hourly_rate is not None:
        conditions.append("f.hourly_rate <= ?")
        sql_parameters.append(max_hourly_rate)
    if currency:
        conditions.append("f.currency = ? COLLATE NOCASE")
        sql_parameters.append(currency)
    if location:
        conditions.append("f.location LIKE ? COLLATE NOCASE")
        sql_parameters.append(f"%{location}%")

    query = (
        """SELECT f.id AS freelancer_id, f.name, f.work_field, f.location,
                  f.skills_json, f.hourly_rate, f.currency,
                  f.availability_status, e.embedding_model, e.embedding_json,
                  e.project_embedding_json,
                  (SELECT title FROM projects
                   WHERE freelancer_id = f.id AND is_public = 1
                   ORDER BY id LIMIT 1) AS sample_project
           FROM freelancer_embeddings AS e
           JOIN freelancers AS f ON f.id = e.freelancer_id
           WHERE """
        + " AND ".join(conditions)
        + " ORDER BY f.id, e.created_at DESC, e.id DESC"
    )

    with database_session(database_path) as connection:
        rows = connection.execute(query, sql_parameters).fetchall()

    if not rows:
        return []

    token = settings.hf_token
    if not token:
        raise RuntimeError("HF_TOKEN is missing from .env or the environment.")
    client = InferenceClient(provider="hf-inference", api_key=token)
    prompt_vector = [
        float(value)
        for value in client.feature_extraction(prompt, model=EMBEDDING_MODEL)
    ]

    matches = []
    seen_freelancers = set()
    for row in rows:
        freelancer_id = row["freelancer_id"]
        if freelancer_id in seen_freelancers:
            continue
        seen_freelancers.add(freelancer_id)

        profile_score = cosine_similarity(
            prompt_vector, json.loads(row["embedding_json"])
        )
        project_score = None
        if row["project_embedding_json"]:
            project_score = cosine_similarity(
                prompt_vector, json.loads(row["project_embedding_json"])
            )
        combined_score = (
            (profile_score + project_score) / 2
            if project_score is not None
            else profile_score
        )
        matches.append(
            {
                "freelancer_id": freelancer_id,
                "name": row["name"],
                "work_field": row["work_field"],
                "location": row["location"],
                "skills": json.loads(row["skills_json"]),
                "hourly_rate": row["hourly_rate"],
                "currency": row["currency"],
                "availability_status": row["availability_status"],
                "sample_project": row["sample_project"],
                "profile_score": profile_score,
                "project_score": project_score,
                "combined_score": combined_score,
            }
        )

    matches.sort(key=lambda item: item["combined_score"], reverse=True)
    return matches if top is None else matches[:top]


def verify_candidate_batch(
    freelancer_ids: list[str],
    *,
    availability_status: str | None = None,
    work_field: str | None = None,
    min_hourly_rate: float | None = None,
    max_hourly_rate: float | None = None,
    currency: str | None = None,
    location: str | None = None,
    required_skills: list[str] | None = None,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> list[dict[str, object]]:
    """Return candidate records that pass explicit database-backed constraints."""
    if not freelancer_ids:
        return []
    if availability_status not in {None, "available", "partial", "unavailable"}:
        raise ValueError("availability_status must be available, partial, or unavailable.")
    if min_hourly_rate is not None and min_hourly_rate < 0:
        raise ValueError("min_hourly_rate cannot be negative.")
    if max_hourly_rate is not None and max_hourly_rate < 0:
        raise ValueError("max_hourly_rate cannot be negative.")
    if min_hourly_rate is not None and max_hourly_rate is not None and min_hourly_rate > max_hourly_rate:
        raise ValueError("min_hourly_rate cannot exceed max_hourly_rate.")

    conditions = [f"f.id IN ({', '.join('?' for _ in freelancer_ids)})"]
    parameters: list[object] = list(freelancer_ids)
    if availability_status:
        conditions.append("f.availability_status = ?")
        parameters.append(availability_status)
    if work_field:
        conditions.append("f.work_field = ? COLLATE NOCASE")
        parameters.append(work_field)
    if min_hourly_rate is not None:
        conditions.append("f.hourly_rate > ?")
        parameters.append(min_hourly_rate)
    if max_hourly_rate is not None:
        conditions.append("f.hourly_rate <= ?")
        parameters.append(max_hourly_rate)
    if currency:
        conditions.append("f.currency = ? COLLATE NOCASE")
        parameters.append(currency)
    if location:
        conditions.append("f.location LIKE ? COLLATE NOCASE")
        parameters.append(f"%{location}%")

    with database_session(database_path) as connection:
        rows = connection.execute(
            """SELECT f.id AS freelancer_id, f.name, f.work_field, f.location,
                      f.skills_json, f.hourly_rate, f.currency,
                      f.availability_status
               FROM freelancers AS f
               WHERE """ + " AND ".join(conditions),
            parameters,
        ).fetchall()
        project_rows = connection.execute(
            f"""SELECT freelancer_id, skills_used_json FROM projects
                WHERE is_public = 1 AND freelancer_id IN
                ({', '.join('?' for _ in freelancer_ids)})""",
            freelancer_ids,
        ).fetchall()

    project_skills: dict[str, set[str]] = {}
    for project in project_rows:
        skills = project_skills.setdefault(project["freelancer_id"], set())
        skills.update(
            skill.casefold()
            for skill in json.loads(project["skills_used_json"] or "[]")
        )

    required = {skill.strip().casefold() for skill in required_skills or [] if skill.strip()}
    verified = []
    for row in rows:
        profile_skills = {
            skill.casefold() for skill in json.loads(row["skills_json"] or "[]")
        }
        if not required.issubset(profile_skills | project_skills.get(row["freelancer_id"], set())):
            continue
        verified.append(dict(row))
    return verified


def verified_semantic_search(
    prompt: str,
    *,
    top: int = 5,
    availability_status: str | None = None,
    work_field: str | None = None,
    min_hourly_rate: float | None = None,
    max_hourly_rate: float | None = None,
    currency: str | None = None,
    location: str | None = None,
    required_skills: list[str] | None = None,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    _ranked_candidates: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Rank once, then widen SQL-verification batches until enough pass or all are checked."""
    if top < 1:
        raise ValueError("top must be at least 1.")
    ranked = (
        _ranked_candidates
        if _ranked_candidates is not None
        else match_freelancers(prompt, top=None, database_path=database_path)
    )
    requested_constraints = {
        "availability_status": availability_status,
        "work_field": work_field,
        "min_hourly_rate": min_hourly_rate,
        "max_hourly_rate": max_hourly_rate,
        "currency": currency,
        "location": location,
        "required_skills": required_skills or [],
    }
    if not ranked:
        return {
            "status": "no_candidates",
            "attempts": 0,
            "candidates_examined": 0,
            "constraints": requested_constraints,
            "matches": [],
        }

    verified_matches = []
    offset = 0
    batch_size = max(5, top)
    attempts = 0
    while offset < len(ranked) and len(verified_matches) < top:
        batch = ranked[offset : offset + batch_size]
        attempts += 1
        passing_rows = verify_candidate_batch(
            [match["freelancer_id"] for match in batch],
            availability_status=availability_status,
            work_field=work_field,
            min_hourly_rate=min_hourly_rate,
            max_hourly_rate=max_hourly_rate,
            currency=currency,
            location=location,
            required_skills=required_skills,
            database_path=database_path,
        )
        passing_ids = {row["freelancer_id"] for row in passing_rows}
        evidence_by_id = {row["freelancer_id"]: row for row in passing_rows}
        for match in batch:
            freelancer_id = match["freelancer_id"]
            if freelancer_id not in passing_ids:
                continue
            verified_matches.append(
                {
                    **match,
                    **evidence_by_id[freelancer_id],
                    "verified": True,
                }
            )
            if len(verified_matches) == top:
                break
        offset += len(batch)
        batch_size *= 2

    status = (
        "verified"
        if len(verified_matches) >= top
        else "partial"
        if verified_matches
        else "no_verified_matches"
    )
    return {
        "status": status,
        "attempts": attempts,
        "candidates_examined": offset,
        "constraints": requested_constraints,
        "matches": verified_matches,
    }


def constraint_relaxation_variants(
    constraints: dict[str, object],
) -> list[tuple[dict[str, object], dict[str, object]]]:
    """Return predictable alternatives that relax exactly one requirement.

    Currency is deliberately not relaxed on its own because comparing numeric
    rates across currencies would be misleading.  When several skills are
    mandatory, each alternative removes only one skill instead of dropping the
    entire skill requirement.
    """
    variants: list[tuple[dict[str, object], dict[str, object]]] = []
    availability = constraints.get("availability_status")
    if availability is not None:
        if availability == "available":
            changed = dict(constraints)
            changed["availability_status"] = "partial"
            variants.append((
                changed,
                {
                    "field": "availability_status",
                    "original_value": availability,
                    "applied_value": "partial",
                },
            ))
        changed = dict(constraints)
        changed.pop("availability_status", None)
        variants.append((
            changed,
            {
                "field": "availability_status",
                "original_value": availability,
                "applied_value": None,
            },
        ))

    priority = (
        "max_hourly_rate",
        "min_hourly_rate",
        "location",
        "work_field",
    )
    for field in priority:
        if field not in constraints:
            continue
        changed = dict(constraints)
        original_value = changed.pop(field)
        variants.append((
            changed,
            {
                "field": field,
                "original_value": original_value,
                "applied_value": None,
            },
        ))

    skills = constraints.get("required_skills")
    if isinstance(skills, list):
        for skill in skills:
            remaining = [item for item in skills if item != skill]
            changed = dict(constraints)
            if remaining:
                changed["required_skills"] = remaining
            else:
                changed.pop("required_skills", None)
            variants.append((
                changed,
                {
                    "field": "required_skills",
                    "original_value": skill,
                    "applied_value": remaining or None,
                },
            ))
    return variants


def relaxation_note(relaxation: dict[str, object]) -> str:
    """Create a user-facing disclosure for one controlled relaxation."""
    field = str(relaxation["field"])
    value = relaxation.get("original_value")
    applied = relaxation.get("applied_value")
    if field == "availability_status" and applied is not None:
        return (
            "No candidate satisfied every exact requirement, so the fallback search "
            f"changed availability from '{value}' to '{applied}'. All other constraints remained active."
        )
    descriptions = {
        "availability_status": f"availability '{value}'",
        "max_hourly_rate": f"the maximum hourly rate of {value}",
        "min_hourly_rate": f"the minimum hourly rate of {value}",
        "location": f"location '{value}'",
        "work_field": f"work field '{value}'",
        "required_skills": f"required skill '{value}'",
    }
    return (
        "No candidate satisfied every exact requirement, so the fallback search "
        f"relaxed {descriptions.get(field, field)}. All other constraints remained active."
    )


def adaptive_verified_semantic_search(
    prompt: str,
    *,
    top: int = 5,
    availability_status: str | None = None,
    work_field: str | None = None,
    min_hourly_rate: float | None = None,
    max_hourly_rate: float | None = None,
    currency: str | None = None,
    location: str | None = None,
    required_skills: list[str] | None = None,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> dict[str, object]:
    """Try exact constraints, then the first viable one-constraint fallback.

    The query embedding and semantic ranking are created once. Every relaxation
    is evaluated with SQL against that same ranking, so fallback checks do not
    consume additional embedding-inference calls.
    """
    active_constraints: dict[str, object] = {
        key: value
        for key, value in {
            "availability_status": availability_status,
            "work_field": work_field,
            "min_hourly_rate": min_hourly_rate,
            "max_hourly_rate": max_hourly_rate,
            "currency": currency,
            "location": location,
            "required_skills": required_skills or None,
        }.items()
        if value is not None
    }
    ranked = match_freelancers(prompt, top=None, database_path=database_path)

    def search_with(filters: dict[str, object]) -> dict[str, object]:
        return verified_semantic_search(
            prompt,
            top=top,
            database_path=database_path,
            _ranked_candidates=ranked,
            **filters,
        )

    exact = search_with(active_constraints)
    exact.update({
        "original_constraints": dict(active_constraints),
        "applied_constraints": dict(active_constraints),
        "relaxed_constraints": [],
        "constraint_notes": [],
        "relaxation_attempts": [],
    })
    if exact["matches"] or not active_constraints:
        return exact

    attempts: list[dict[str, object]] = []
    for relaxed_filters, relaxation in constraint_relaxation_variants(active_constraints):
        alternative = search_with(relaxed_filters)
        attempts.append({
            **relaxation,
            "status": alternative["status"],
            "matches_found": len(alternative["matches"]),
        })
        if not alternative["matches"]:
            continue
        alternative.update({
            "status": "relaxed",
            "original_constraints": dict(active_constraints),
            "applied_constraints": dict(relaxed_filters),
            "relaxed_constraints": [relaxation],
            "constraint_notes": [relaxation_note(relaxation)],
            "relaxation_attempts": attempts,
        })
        return alternative

    exact["relaxation_attempts"] = attempts
    return exact


def database_catalog(database_path: str | Path = DEFAULT_DATABASE_PATH) -> dict[str, object]:
    """Read current coverage instead of hard-coding the professions we support."""
    with database_session(database_path) as connection:
        fields = connection.execute(
            "SELECT work_field, COUNT(*) AS count FROM freelancers GROUP BY work_field ORDER BY work_field"
        ).fetchall()
        total = connection.execute("SELECT COUNT(*) FROM freelancers").fetchone()[0]
    return {"freelancer_count": total, "work_fields": [dict(row) for row in fields]}


_EVIDENCE_STOP_WORDS = {
    "a", "an", "and", "for", "from", "in", "of", "on", "or", "the",
    "to", "with", "who", "professional", "freelancer", "project",
}


def _project_relevance_score(project: dict[str, object], query: str) -> int:
    """Score stored project text against the current retrieval description."""
    query_terms = {
        token
        for token in re.findall(r"[\w+#.-]+", query.casefold())
        if len(token) > 1 and token not in _EVIDENCE_STOP_WORDS
    }
    if not query_terms:
        return 0

    weighted_fields = (
        (project.get("skills", []), 5),
        (project.get("title", ""), 3),
        (project.get("work_field", ""), 3),
        (project.get("role", ""), 3),
        (project.get("client_industry", ""), 2),
        (project.get("detail", ""), 1),
    )
    score = 0
    for value, weight in weighted_fields:
        text = " ".join(str(item) for item in value) if isinstance(value, list) else str(value)
        field_terms = set(re.findall(r"[\w+#.-]+", text.casefold()))
        score += weight * len(query_terms & field_terms)
    return score


def candidate_evidence(
    matches: list[dict[str, object]],
    query: str = "",
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> list[dict[str, object]]:
    """Attach the most query-relevant public evidence without private data."""
    if not matches:
        return []
    ids = [match["freelancer_id"] for match in matches]
    placeholders = ", ".join("?" for _ in ids)
    with database_session(database_path) as connection:
        profiles = {
            row["id"]: dict(row)
            for row in connection.execute(
                f"SELECT id, bio, experience_years, languages_json FROM freelancers WHERE id IN ({placeholders})",
                ids,
            )
        }
        projects = connection.execute(
            f"""SELECT id, freelancer_id, title, detail, work_field, skills_used_json,
                       role, client_industry, completed_at
                FROM projects WHERE is_public = 1 AND freelancer_id IN ({placeholders})
                ORDER BY freelancer_id, completed_at DESC, id""",
            ids,
        ).fetchall()
    by_person: dict[str, list[dict[str, object]]] = {}
    for project in projects:
        public = by_person.setdefault(project["freelancer_id"], [])
        public.append({
            "id": project["id"], "title": project["title"],
            "detail": project["detail"][:1200], "work_field": project["work_field"],
            "skills": json.loads(project["skills_used_json"] or "[]"),
            "role": project["role"], "client_industry": project["client_industry"],
            "completed_at": project["completed_at"],
        })
    for public in by_person.values():
        public.sort(
            key=lambda project: _project_relevance_score(project, query),
            reverse=True,
        )
        del public[4:]
    enriched = []
    for match in matches:
        profile = profiles.get(match["freelancer_id"])
        if profile is None:
            continue
        enriched.append({
            **{key: value for key, value in match.items() if key != "skills_json"},
            "bio": profile["bio"][:1200], "experience_years": profile["experience_years"],
            "languages": json.loads(profile["languages_json"] or "[]"),
            "public_projects": by_person.get(match["freelancer_id"], []),
        })
    return enriched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", help="Client request to match against freelancers")
    parser.add_argument("--top", type=int, default=5, help="Number of results (default: 5)")
    arguments = parser.parse_args()
    try:
        matches = match_freelancers(arguments.prompt, top=arguments.top)
    except Exception as error:
        parser.exit(1, f"Matching failed: {error}\n")

    print(f"Client request: {arguments.prompt}\n")
    if not matches:
        print("No freelancers matched the request.")
        return
    for rank, match in enumerate(matches, start=1):
        project_score = match["project_score"]
        print(
            f"{rank}. {match['name']} ({match['freelancer_id']}) - "
            f"{match['work_field']}"
        )
        print(f"   Skills: {', '.join(match['skills'])}")
        print(f"   Example project: {match['sample_project'] or 'none'}")
        print(
            f"   Similarity: {match['combined_score']:.3f} "
            f"(profile {match['profile_score']:.3f}, "
            f"projects {project_score:.3f})"
            if project_score is not None
            else f"   Similarity: {match['combined_score']:.3f} "
                 f"(profile only; no project vector)"
        )


if __name__ == "__main__":
    main()
