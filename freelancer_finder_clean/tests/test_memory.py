"""Tests for persistent, bounded conversation memory."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from freelancer_finder.data.database import initialize_database
from freelancer_finder.data.memory import (
    conversation_id,
    load_constraints,
    load_messages,
    save_constraints,
    save_exchange,
)


class ConversationMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "memory.sqlite3"
        initialize_database(self.database_path)
        self.thread_id = "test-thread-1234"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_exchange_survives_a_new_database_connection(self) -> None:
        save_exchange(
            self.thread_id,
            "Find a Django developer",
            "Amina is a possible match.",
            database_path=self.database_path,
        )

        self.assertEqual(
            load_messages(
                self.thread_id,
                database_path=self.database_path,
            ),
            [
                {"role": "user", "content": "Find a Django developer"},
                {"role": "assistant", "content": "Amina is a possible match."},
            ],
        )

    def test_history_limit_keeps_the_newest_messages_in_order(self) -> None:
        save_exchange(
            self.thread_id,
            "First question",
            "First answer",
            database_path=self.database_path,
        )
        save_exchange(
            self.thread_id,
            "Follow-up question",
            "Follow-up answer",
            database_path=self.database_path,
        )

        self.assertEqual(
            load_messages(
                self.thread_id,
                limit=2,
                database_path=self.database_path,
            ),
            [
                {"role": "user", "content": "Follow-up question"},
                {"role": "assistant", "content": "Follow-up answer"},
            ],
        )

    def test_invalid_conversation_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "conversation_id"):
            conversation_id("../not-a-thread")

    def test_confirmed_constraints_survive_outside_message_window(self) -> None:
        save_constraints(
            self.thread_id,
            [
                {
                    "field": "location",
                    "value": "Portugal",
                    "source_quote": "in Portugal",
                },
                {
                    "field": "max_hourly_rate",
                    "value": 45,
                    "source_quote": "under 45 EUR per hour",
                },
                {
                    "field": "currency",
                    "value": "EUR",
                    "source_quote": "under 45 EUR per hour",
                },
            ],
            database_path=self.database_path,
        )
        for index in range(6):
            save_exchange(
                self.thread_id,
                f"Later question {index}",
                f"Later answer {index}",
                database_path=self.database_path,
            )

        self.assertNotIn(
            "in Portugal",
            " ".join(
                item["content"]
                for item in load_messages(
                    self.thread_id, limit=10, database_path=self.database_path
                )
            ),
        )
        self.assertEqual(
            load_constraints(self.thread_id, database_path=self.database_path),
            [
                {
                    "field": "currency",
                    "value": "EUR",
                    "source_quote": "under 45 EUR per hour",
                },
                {
                    "field": "location",
                    "value": "Portugal",
                    "source_quote": "in Portugal",
                },
                {
                    "field": "max_hourly_rate",
                    "value": 45,
                    "source_quote": "under 45 EUR per hour",
                },
            ],
        )

    def test_constraint_snapshot_replaces_corrected_values(self) -> None:
        save_constraints(
            self.thread_id,
            [{"field": "location", "value": "Portugal", "source_quote": "Portugal"}],
            database_path=self.database_path,
        )
        save_constraints(
            self.thread_id,
            [{"field": "location", "value": "France", "source_quote": "France"}],
            database_path=self.database_path,
        )

        self.assertEqual(
            load_constraints(self.thread_id, database_path=self.database_path),
            [{"field": "location", "value": "France", "source_quote": "France"}],
        )


if __name__ == "__main__":
    unittest.main()
