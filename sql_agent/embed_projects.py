"""Store one combined public-project embedding per freelancer.

Run from the repository root:
    python -m sql_agent.embed_projects
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict

from dotenv import load_dotenv
from huggingface_hub import InferenceClient

try:
    from .database import DEFAULT_DATABASE_PATH, database_session, initialize_database
except ImportError:
    from database import DEFAULT_DATABASE_PATH, database_session, initialize_database


EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def project_text(project: dict[str, object]) -> str:
    """Format searchable project fields without embedding image or URL data."""
    fields = (
        ("Title", project["title"]),
        ("Detail", project["detail"]),
        ("Work field", project["work_field"]),
        ("Skills used", ", ".join(json.loads(project["skills_used_json"] or "[]"))),
        ("Role", project["role"]),
        ("Client industry", project["client_industry"]),
    )
    return "\n".join(f"{label}: {value}" for label, value in fields if value)


def embed_projects() -> tuple[int, int]:
    """Update saved freelancer embeddings with their combined project vector."""
    load_dotenv(DEFAULT_DATABASE_PATH.parent / ".env")
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is missing from sql_agent/.env or the environment.")

    initialize_database()
    with database_session() as connection:
        embedding_rows = connection.execute(
            "SELECT id, freelancer_id, embedding_model FROM freelancer_embeddings ORDER BY freelancer_id"
        ).fetchall()
        projects = connection.execute(
            """SELECT id, freelancer_id, title, detail, work_field,
                      skills_used_json, role, client_industry
               FROM projects WHERE is_public = 1
               ORDER BY freelancer_id, id"""
        ).fetchall()

    if any(row["embedding_model"] != EMBEDDING_MODEL for row in embedding_rows):
        raise ValueError(
            f"Saved profile vectors must use {EMBEDDING_MODEL} to share a model "
            "with project vectors."
        )

    projects_by_freelancer = defaultdict(list)
    for project in projects:
        projects_by_freelancer[project["freelancer_id"]].append(dict(project))

    targets = []
    for row in embedding_rows:
        related = projects_by_freelancer[row["freelancer_id"]]
        if related:
            content = "\n\n".join(
                f"Project {index}\n{project_text(project)}"
                for index, project in enumerate(related, start=1)
            )
            targets.append((row["id"], row["freelancer_id"], content))

    if not targets:
        return 0, len(embedding_rows)

    client = InferenceClient(provider="hf-inference", api_key=token)
    vectors = client.feature_extraction(
        [content for _, _, content in targets], model=EMBEDDING_MODEL
    )
    if len(vectors) != len(targets):
        raise RuntimeError("Embedding provider returned an unexpected number of vectors.")

    with database_session() as connection:
        for (embedding_id, _, content), vector in zip(targets, vectors, strict=True):
            connection.execute(
                """UPDATE freelancer_embeddings
                   SET project_contents = ?, project_embedding_json = ?
                   WHERE id = ?""",
                (content, json.dumps([float(value) for value in vector]), embedding_id),
            )
    return len(targets), len(embedding_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    updated, total = embed_projects()
    print(f"Saved project embeddings for {updated} of {total} freelancers.")


if __name__ == "__main__":
    main()
