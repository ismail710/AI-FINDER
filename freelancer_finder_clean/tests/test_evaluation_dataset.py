"""Structural checks for the manual LLM evaluation corpus."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


CASES_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "client_conversations.json"


class EvaluationDatasetTests(unittest.TestCase):
    def test_corpus_has_twenty_unique_realistic_cases(self) -> None:
        cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

        self.assertEqual(len(cases), 20)
        self.assertEqual(len({case["id"] for case in cases}), 20)
        self.assertTrue({"en", "fr"}.issubset({case["language"] for case in cases}))
        self.assertTrue(any(case.get("history") for case in cases))
        self.assertTrue(any(case.get("confirmed_constraints") for case in cases))
        self.assertGreaterEqual(
            sum("expected_full_status" in case for case in cases), 2
        )


if __name__ == "__main__":
    unittest.main()
