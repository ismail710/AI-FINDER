"""Print a human-readable sample without dumping full embedding vectors."""

import json

from freelancer_finder.data.database import database_session


if __name__ == "__main__":
    with database_session() as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "freelancers",
                "projects",
                "freelancer_embeddings",
                "conversations",
                "conversation_messages",
            )
        }
        rows = connection.execute(
            """SELECT f.id, f.name, f.work_field, f.skills_json,
                      e.dimensions, length(e.project_embedding_json) AS project_vector_chars
                 FROM freelancers AS f
                 LEFT JOIN freelancer_embeddings AS e ON e.freelancer_id = f.id
                 ORDER BY f.id LIMIT 5"""
        ).fetchall()
    print(json.dumps({"counts": counts, "sample": [dict(row) for row in rows]}, indent=2))
