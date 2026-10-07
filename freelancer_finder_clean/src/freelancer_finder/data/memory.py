"""Persistent, bounded conversation memory backed by the local SQLite file."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import DEFAULT_DATABASE_PATH
from .database import database_session


CONVERSATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
CONSTRAINT_FIELDS = {
    "availability_status", "work_field", "min_hourly_rate", "max_hourly_rate",
    "currency", "location", "required_skills",
}


def conversation_id(value: object | None = None) -> str:
    """Validate a supplied thread ID or create a new unpredictable one."""
    if value is None or value == "":
        return str(uuid.uuid4())
    if not isinstance(value, str) or not CONVERSATION_ID_PATTERN.fullmatch(value):
        raise ValueError(
            "conversation_id must contain 8-64 letters, numbers, hyphens, or underscores."
        )
    return value


def load_messages(
    thread_id: str,
    *,
    limit: int = 10,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> list[dict[str, str]]:
    """Return the newest messages in chronological order for an LLM or UI."""
    validated_id = conversation_id(thread_id)
    if not 1 <= limit <= 100:
        raise ValueError("Memory limit must be between 1 and 100 messages.")
    with database_session(database_path) as connection:
        rows = connection.execute(
            """SELECT role, content
                 FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?""",
            (validated_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def save_exchange(
    thread_id: str,
    user_message: str,
    assistant_message: str,
    *,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> None:
    """Atomically append one successful user/assistant exchange."""
    validated_id = conversation_id(thread_id)
    if not user_message.strip() or not assistant_message.strip():
        raise ValueError("Conversation messages cannot be empty.")
    timestamp = datetime.now(timezone.utc).isoformat()
    with database_session(database_path) as connection:
        connection.execute(
            """INSERT INTO conversations (id, created_at, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at""",
            (validated_id, timestamp, timestamp),
        )
        connection.executemany(
            """INSERT INTO conversation_messages
                   (conversation_id, role, content, created_at)
               VALUES (?, ?, ?, ?)""",
            (
                (validated_id, "user", user_message, timestamp),
                (validated_id, "assistant", assistant_message, timestamp),
            ),
        )


def load_constraints(
    thread_id: str,
    *,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> list[dict[str, Any]]:
    """Return the active, user-sourced requirements for a conversation."""
    validated_id = conversation_id(thread_id)
    with database_session(database_path) as connection:
        rows = connection.execute(
            """SELECT field, value_json, source_quote
                 FROM conversation_constraints
                WHERE conversation_id = ?
                ORDER BY field""",
            (validated_id,),
        ).fetchall()
    return [
        {
            "field": row["field"],
            "value": json.loads(row["value_json"]),
            "source_quote": row["source_quote"],
        }
        for row in rows
    ]


def save_constraints(
    thread_id: str,
    constraints: list[dict[str, Any]],
    *,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
) -> None:
    """Replace a conversation's active requirements with a validated plan snapshot."""
    validated_id = conversation_id(thread_id)
    timestamp = datetime.now(timezone.utc).isoformat()
    prepared: list[tuple[str, str, str, str, str]] = []
    seen: set[str] = set()
    for constraint in constraints:
        field = constraint.get("field")
        source_quote = constraint.get("source_quote")
        if field not in CONSTRAINT_FIELDS or field in seen:
            raise ValueError(f"Invalid or duplicate constraint field: {field}")
        if not isinstance(source_quote, str) or not source_quote.strip():
            raise ValueError(f"{field}: source_quote must be nonempty text")
        seen.add(field)
        prepared.append(
            (
                validated_id,
                field,
                json.dumps(constraint.get("value"), ensure_ascii=False),
                source_quote,
                timestamp,
            )
        )

    with database_session(database_path) as connection:
        connection.execute(
            """INSERT INTO conversations (id, created_at, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at""",
            (validated_id, timestamp, timestamp),
        )
        connection.execute(
            "DELETE FROM conversation_constraints WHERE conversation_id = ?",
            (validated_id,),
        )
        connection.executemany(
            """INSERT INTO conversation_constraints
                   (conversation_id, field, value_json, source_quote, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            prepared,
        )
