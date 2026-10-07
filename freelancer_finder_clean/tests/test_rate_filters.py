"""SQL verification tests for minimum and maximum hourly-rate bounds."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from freelancer_finder.data.database import database_session, initialize_database
from freelancer_finder.matching.search import verify_candidate_batch


class RateFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "rates.sqlite3"
        initialize_database(self.database_path)
        with database_session(self.database_path) as connection:
            connection.executemany(
                """INSERT INTO freelancers (
                       id, name, email, bio, skills_json, work_field,
                       hourly_rate, currency, availability_status
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    (
                        "low-rate",
                        "Low Rate",
                        "low@example.test",
                        "Django developer",
                        json.dumps(["Python", "Django"]),
                        "Software development",
                        40,
                        "USD",
                        "available",
                    ),
                    (
                        "high-rate",
                        "High Rate",
                        "high@example.test",
                        "Django developer",
                        json.dumps(["Python", "Django"]),
                        "Software development",
                        75,
                        "USD",
                        "available",
                    ),
                ),
            )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_minimum_rate_excludes_lower_rate_candidate(self) -> None:
        matches = verify_candidate_batch(
            ["low-rate", "high-rate"],
            availability_status="available",
            min_hourly_rate=60,
            currency="USD",
            required_skills=["Django"],
            database_path=self.database_path,
        )

        self.assertEqual(
            [match["freelancer_id"] for match in matches],
            ["high-rate"],
        )

    def test_invalid_rate_range_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            verify_candidate_batch(
                ["low-rate", "high-rate"],
                min_hourly_rate=80,
                max_hourly_rate=60,
                database_path=self.database_path,
            )


if __name__ == "__main__":
    unittest.main()

