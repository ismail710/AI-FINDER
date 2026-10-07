"""Unit tests for the one-profile/one-vector embedding contract."""

from __future__ import annotations

import unittest

from freelancer_finder.embeddings.profiles import create_profile_embedding


class RecordingProvider:
    """Avoid a network call while recording the exact embedded document."""

    def __init__(self) -> None:
        self.documents: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.documents.append(text)
        return [0.25, 0.5, 0.75]


class ProfileEmbeddingTests(unittest.TestCase):
    def test_selected_columns_form_one_vector_owned_by_freelancer(self) -> None:
        provider = RecordingProvider()
        row = {
            "id": "freelancer_007",
            "name": "Example Person",
            "bio": "Builds accessible web products.",
            "skills_json": '["Python", "Accessibility"]',
            "private_note": "must never be embedded",
        }

        record = create_profile_embedding(
            row,
            ("name", "bio", "skills_json"),
            provider,
        )

        self.assertEqual(record.freelancer_id, "freelancer_007")
        self.assertEqual(record.vector, [0.25, 0.5, 0.75])
        self.assertEqual(len(provider.documents), 1)
        self.assertIn("Name: Example Person", record.contents)
        self.assertIn("Skills: Python, Accessibility", record.contents)
        self.assertNotIn("private_note", record.contents)
        self.assertEqual(
            record.metadata["source_columns"],
            ["name", "bio", "skills_json"],
        )


if __name__ == "__main__":
    unittest.main()

