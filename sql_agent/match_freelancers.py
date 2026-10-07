"""Rank freelancers for a client request using saved profile and project vectors.

Run from the repository root:
    python -m sql_agent.match_freelancers "I need a Python Django developer"
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

try:
    from .database import DEFAULT_DATABASE_PATH, database_session
    from .embed_projects import EMBEDDING_MODEL
except ImportError:
    from database import DEFAULT_DATABASE_PATH, database_session
    from embed_projects import EMBEDDING_MODEL


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
    if max_hourly_rate is not None and max_hourly_rate < 0:
        raise ValueError("max_hourly_rate cannot be negative.")

    conditions = ["e.embedding_model = ?"]
    sql_parameters: list[object] = [EMBEDDING_MODEL]
    if availability_status:
        conditions.append("f.availability_status = ?")
        sql_parameters.append(availability_status)
    if work_field:
        conditions.append("f.work_field = ? COLLATE NOCASE")
        sql_parameters.append(work_field)
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

    load_dotenv(DEFAULT_DATABASE_PATH.parent / ".env")
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is missing from sql_agent/.env or the environment.")
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
    if max_hourly_rate is not None and max_hourly_rate < 0:
        raise ValueError("max_hourly_rate cannot be negative.")

    conditions = [f"f.id IN ({', '.join('?' for _ in freelancer_ids)})"]
    parameters: list[object] = list(freelancer_ids)
    if availability_status:
        conditions.append("f.availability_status = ?")
        parameters.append(availability_status)
    if work_field:
        conditions.append("f.work_field = ? COLLATE NOCASE")
        parameters.append(work_field)
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
    max_hourly_rate: float | None = None,
    currency: str | None = None,
    location: str | None = None,
    required_skills: list[str] | None = None,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> dict[str, object]:
    """Rank once, then widen SQL-verification batches until enough pass or all are checked."""
    if top < 1:
        raise ValueError("top must be at least 1.")
    ranked = match_freelancers(prompt, top=None, database_path=database_path)
    requested_constraints = {
        "availability_status": availability_status,
        "work_field": work_field,
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


def database_catalog(database_path: str | Path = DEFAULT_DATABASE_PATH) -> dict[str, object]:
    """Read current coverage instead of hard-coding the professions we support."""
    with database_session(database_path) as connection:
        fields = connection.execute(
            "SELECT work_field, COUNT(*) AS count FROM freelancers GROUP BY work_field ORDER BY work_field"
        ).fetchall()
        total = connection.execute("SELECT COUNT(*) FROM freelancers").fetchone()[0]
    return {"freelancer_count": total, "work_fields": [dict(row) for row in fields]}


def candidate_evidence(
    matches: list[dict[str, object]],
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> list[dict[str, object]]:
    """Attach public portfolio evidence without exposing vectors or private contact data."""
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
        if len(public) < 4:
            public.append({
                "id": project["id"], "title": project["title"],
                "detail": project["detail"][:1200], "work_field": project["work_field"],
                "skills": json.loads(project["skills_used_json"] or "[]"),
                "role": project["role"], "client_industry": project["client_industry"],
                "completed_at": project["completed_at"],
            })
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
