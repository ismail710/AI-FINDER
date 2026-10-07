"""Tests for deterministic conversation-recall questions."""

from __future__ import annotations

import unittest

from freelancer_finder.web.server import _previous_question_answer


class WebMemoryTests(unittest.TestCase):
    def test_previous_question_is_recalled(self) -> None:
        history = [
            {"role": "user", "content": "Find a Django developer"},
            {"role": "assistant", "content": "Amina is a possible match."},
        ]

        self.assertEqual(
            _previous_question_answer("What did I ask before?", history),
            'Your previous question was: "Find a Django developer"',
        )

    def test_multiple_questions_can_be_listed(self) -> None:
        history = [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question"},
            {"role": "assistant", "content": "Second answer"},
        ]

        answer = _previous_question_answer("List my previous questions", history)

        self.assertIn("1. First question", answer or "")
        self.assertIn("2. Second question", answer or "")

    def test_unrelated_question_is_not_intercepted(self) -> None:
        self.assertIsNone(
            _previous_question_answer(
                "Find a Python developer",
                [{"role": "user", "content": "Hello"}],
            )
        )


if __name__ == "__main__":
    unittest.main()

