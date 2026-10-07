"""SQLite connection and initialization helpers for the SQL agent.

The module uses only Python's standard-library :mod:`sqlite3` package.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..config import DEFAULT_DATABASE_PATH, SCHEMA_PATH

def get_connection(database_path: str | Path = DEFAULT_DATABASE_PATH) -> sqlite3.Connection:
    """Return a configured SQLite connection to the freelancer database.

    Foreign keys are enabled separately for every SQLite connection, so callers
    should always obtain connections through this function.
    """
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: str | Path = DEFAULT_DATABASE_PATH) -> Path:
    """Create or upgrade the local freelancer SQLite database from ``schema.sql``."""
    path = Path(database_path)
    with database_session(path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(freelancer_embeddings)")
        }
        if "project_contents" not in columns:
            connection.execute(
                "ALTER TABLE freelancer_embeddings ADD COLUMN project_contents TEXT"
            )
        if "project_embedding_json" not in columns:
            connection.execute(
                "ALTER TABLE freelancer_embeddings ADD COLUMN project_embedding_json TEXT"
            )
    return path


@contextmanager
def database_session(database_path: str | Path = DEFAULT_DATABASE_PATH) -> Iterator[sqlite3.Connection]:
    """Yield a transactional connection and commit on successful completion."""
    connection = get_connection(database_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    database = initialize_database()
    print(f"Freelancer database is ready: {database}")
