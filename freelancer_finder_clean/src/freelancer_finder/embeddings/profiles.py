"""Create and persist one profile embedding per freelancer.

The embedding text is built only from explicitly selected columns.  Each saved
vector includes ``freelancer_id`` so it can always be joined back to SQLite.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from huggingface_hub import InferenceClient

from ..config import DEFAULT_DATABASE_PATH, settings
from ..data.database import database_session, initialize_database


DEFAULT_PROFILE_COLUMNS = (
    "name",
    "bio",
    "work_field",
    "skills_json",
    "experience_years",
    "location",
    "languages_json",
)


class EmbeddingProvider(Protocol):
    """Small interface that keeps embedding creation provider-independent."""

    def embed(self, text: str) -> list[float]: ...


class HuggingFaceEmbeddingProvider:
    """Embedding provider backed by Hugging Face Inference Providers."""

    def __init__(self, token: str, model: str = settings.embedding_model) -> None:
        self.model = model
        self.client = InferenceClient(provider="hf-inference", api_key=token)

    def embed(self, text: str) -> list[float]:
        return [
            float(value)
            for value in self.client.feature_extraction(text, model=self.model)
        ]


@dataclass(frozen=True)
class ProfileEmbedding:
    """A vector plus the identity and source text needed for auditing."""

    id: str
    freelancer_id: str
    contents: str
    vector: list[float]
    metadata: dict[str, Any]


def _display_value(column: str, value: Any) -> str:
    if column.endswith("_json") and isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value
        if isinstance(decoded, list):
            return ", ".join(str(item) for item in decoded)
    return str(value)


def build_profile_text(row: Mapping[str, Any], columns: Sequence[str]) -> str:
    """Join selected columns into one labelled document for one embedding."""
    if not columns:
        raise ValueError("Specify at least one profile column to embed.")
    missing = [column for column in columns if column not in row]
    if missing:
        raise KeyError(f"Columns not found in freelancer row: {missing}")
    parts = []
    for column in columns:
        value = row[column]
        if value is None or not str(value).strip():
            continue
        label = column.removesuffix("_json").replace("_", " ").title()
        parts.append(f"{label}: {_display_value(column, value)}")
    if not parts:
        raise ValueError("The selected columns contain no profile content.")
    return "\n".join(parts)


def create_profile_embedding(
    row: Mapping[str, Any],
    columns: Sequence[str],
    provider: EmbeddingProvider,
) -> ProfileEmbedding:
    """Create one vector by joining the requested fields for one freelancer."""
    freelancer_id = str(row.get("freelancer_id") or row.get("id") or "").strip()
    if not freelancer_id:
        raise ValueError("A profile embedding requires id or freelancer_id.")
    contents = build_profile_text(row, columns)
    vector = provider.embed(contents)
    if not vector:
        raise ValueError("The embedding provider returned an empty vector.")
    created_at = datetime.now(timezone.utc).isoformat()
    return ProfileEmbedding(
        id=str(uuid.uuid4()),
        freelancer_id=freelancer_id,
        contents=contents,
        vector=vector,
        metadata={
            "freelancer_id": freelancer_id,
            "source_columns": list(columns),
            "created_at": created_at,
        },
    )


def save_profile_embedding(
    record: ProfileEmbedding,
    *,
    model: str = settings.embedding_model,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> None:
    """Replace the freelancer's vector for this model in one transaction."""
    with database_session(database_path) as connection:
        connection.execute(
            "DELETE FROM freelancer_embeddings WHERE freelancer_id = ? AND embedding_model = ?",
            (record.freelancer_id, model),
        )
        connection.execute(
            """INSERT INTO freelancer_embeddings (
                   id, freelancer_id, contents, embedding_json, metadata_json,
                   embedding_model, dimensions, created_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id,
                record.freelancer_id,
                record.contents,
                json.dumps(record.vector),
                json.dumps(record.metadata),
                model,
                len(record.vector),
                record.metadata["created_at"],
            ),
        )


def refresh_profile_embeddings(
    columns: Sequence[str] = DEFAULT_PROFILE_COLUMNS,
    *,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> int:
    """Rebuild profile vectors for every freelancer in the database."""
    if not settings.hf_token:
        raise RuntimeError("HF_TOKEN is required to generate embeddings.")
    initialize_database(database_path)
    with database_session(database_path) as connection:
        rows = [dict(row) for row in connection.execute("SELECT * FROM freelancers ORDER BY id")]
    provider = HuggingFaceEmbeddingProvider(settings.hf_token)
    for row in rows:
        save_profile_embedding(
            create_profile_embedding(row, columns, provider),
            database_path=database_path,
        )
    return len(rows)

