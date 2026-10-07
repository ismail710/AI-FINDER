"""Validation checks for the domain-neutral matching workflow."""

from __future__ import annotations

import unittest
import json
from types import SimpleNamespace

from sql_agent.matching_workflow import (
    CandidateDecision,
    EvidenceReference,
    MatchReview,
    diverse_candidates,
    render_recommendation,
    validate_review,
)
from sql_agent.project_intent import (
    HardConstraint,
    SearchPlan,
    constraint_arguments,
    create_search_plan,
    structured_response,
)


def plan(**changes) -> SearchPlan:
    values = {
        "route": "match",
        "goal": "Create a useful client result",
        "professions": ["Relevant professional"],
        "suggested_skills": ["Relevant skill"],
        "portfolio_evidence": ["Comparable completed work"],
        "criteria_to_confirm": [],
        "hard_constraints": [],
        "search_query": "Relevant professional with comparable completed work",
        "questions": ["What outcome matters most?"],
        "reply": "",
    }
    values.update(changes)
    return SearchPlan(**values)


class IntelligentMatchingTests(unittest.TestCase):
    def test_review_batch_preserves_rank_and_adds_profession_diversity(self) -> None:
        matches = [
            {"freelancer_id": "ai1", "work_field": "Data and AI"},
            {"freelancer_id": "ai2", "work_field": "Data and AI"},
            {"freelancer_id": "web1", "work_field": "Software development"},
            {"freelancer_id": "design1", "work_field": "Product design"},
            {"freelancer_id": "ai3", "work_field": "Data and AI"},
        ]
        selected = diverse_candidates(matches, 4)
        self.assertEqual(
            [match["freelancer_id"] for match in selected],
            ["ai1", "web1", "design1", "ai2"],
        )

    def test_openai_compatible_model_receives_json_schema(self) -> None:
        class LocalModel:
            __module__ = "langchain_openai.fake"

            def __init__(self) -> None:
                self.options = None

            def invoke(self, _messages, **options):
                self.options = options
                return SimpleNamespace(content=plan().model_dump_json())

        model = LocalModel()
        result = structured_response(model, "Plan", {}, SearchPlan)
        self.assertEqual(result.route, "match")
        self.assertEqual(model.options["response_format"]["type"], "json_schema")
        self.assertEqual(model.options["response_format"]["json_schema"]["name"], "SearchPlan")

    def test_native_ollama_model_receives_json_schema(self) -> None:
        class LocalModel:
            __module__ = "langchain_ollama.fake"

            def __init__(self) -> None:
                self.options = None

            def invoke(self, _messages, **options):
                self.options = options
                return SimpleNamespace(content=plan().model_dump_json())

        model = LocalModel()
        structured_response(model, "Plan", {}, SearchPlan)
        self.assertEqual(model.options["format"]["title"], "SearchPlan")

    def test_profession_planning_is_not_anchored_to_catalog_categories(self) -> None:
        class LocalModel:
            def __init__(self) -> None:
                self.context = None

            def invoke(self, messages, **_options):
                self.context = json.loads(messages[1]["content"])
                return SimpleNamespace(content=plan().model_dump_json())

        model = LocalModel()
        create_search_plan(
            model,
            "Build a home",
            [],
            {"freelancer_count": 36, "work_fields": [{"work_field": "Software development"}]},
        )
        self.assertNotIn("work_fields", model.context["database_summary"])
        self.assertEqual(model.context["database_summary"]["freelancer_count"], 36)

    def test_worldwide_search_has_no_implicit_location(self) -> None:
        self.assertEqual(constraint_arguments(plan(), ["Find the best person worldwide"]), {})

    def test_explicit_mandatory_skill_is_a_hard_constraint(self) -> None:
        search_plan = plan(hard_constraints=[HardConstraint(
            field="required_skills", value=["Python"], source_quote="must know Python"
        )])
        self.assertEqual(
            constraint_arguments(search_plan, ["The freelancer must know Python"]),
            {"required_skills": ["Python"]},
        )

    def test_inferred_skill_cannot_become_a_hard_constraint(self) -> None:
        search_plan = plan(hard_constraints=[HardConstraint(
            field="required_skills", value=["Python"], source_quote="build a data product"
        )])
        with self.assertRaisesRegex(ValueError, "mandatory wording"):
            constraint_arguments(search_plan, ["Help me build a data product"])

    def test_total_budget_cannot_become_hourly_ceiling(self) -> None:
        search_plan = plan(hard_constraints=[
            HardConstraint(field="max_hourly_rate", value=5000, source_quote="budget is 5000 USD"),
            HardConstraint(field="currency", value="USD", source_quote="budget is 5000 USD"),
        ])
        with self.assertRaisesRegex(ValueError, "total budget"):
            constraint_arguments(search_plan, ["My budget is 5000 USD"])

    def test_review_evidence_must_exist_in_named_source(self) -> None:
        candidates = [{
            "freelancer_id": "f1", "work_field": "Illustration", "skills": ["Watercolor"],
            "bio": "Children's book illustrator", "languages": ["English"],
            "public_projects": [{"id": "p1", "title": "Forest story", "detail": "Painted twelve watercolor scenes"}],
        }]
        valid = MatchReview(action="accept", matches=[CandidateDecision(
            freelancer_id="f1", fit="strong",
            evidence=[EvidenceReference(source="p1", field="detail")],
        )])
        validate_review(valid, candidates)
        invalid = MatchReview(action="accept", matches=[CandidateDecision(
            freelancer_id="f1", fit="strong",
            evidence=[EvidenceReference(source="p1", field="bio")],
        )])
        with self.assertRaisesRegex(ValueError, "evidence reference"):
            validate_review(invalid, candidates)

    def test_retry_must_change_query_and_cannot_recommend(self) -> None:
        candidates = [{
            "freelancer_id": "f1", "work_field": "Illustration", "skills": ["Watercolor"],
            "bio": "Children's book illustrator", "languages": ["English"],
            "public_projects": [{"id": "p1", "detail": "Painted watercolor scenes"}],
        }]
        repeated = MatchReview(
            action="retry", feedback="Try again", revised_query="watercolor illustrator"
        )
        with self.assertRaisesRegex(ValueError, "meaningfully different"):
            validate_review(repeated, candidates, "watercolor illustrator")
        recommending = MatchReview(
            action="retry", feedback="Try a synonym", revised_query="children's book artist",
            matches=[CandidateDecision(
                freelancer_id="f1", fit="partial",
                evidence=[EvidenceReference(source="p1", field="detail")],
                gaps=["No exact publishing evidence"],
            )],
        )
        with self.assertRaisesRegex(ValueError, "must not recommend"):
            validate_review(recommending, candidates, "watercolor illustrator")

    def test_strong_fit_needs_project_evidence(self) -> None:
        candidates = [{
            "freelancer_id": "f1", "work_field": "Illustration", "skills": ["Watercolor"],
            "bio": "Children's book illustrator", "languages": ["English"],
            "public_projects": [{"id": "p1", "detail": "Painted watercolor scenes"}],
        }]
        profile_only = MatchReview(action="accept", matches=[CandidateDecision(
            freelancer_id="f1", fit="strong",
            evidence=[EvidenceReference(source="profile", field="skills")],
        )])
        with self.assertRaisesRegex(ValueError, "public-project evidence"):
            validate_review(profile_only, candidates)

    def test_duplicate_evidence_profiles_are_collapsed(self) -> None:
        candidates = [
            {
                "freelancer_id": freelancer_id,
                "work_field": "Data and AI",
                "skills": ["Python", "Machine learning"],
                "bio": "Data specialist",
                "languages": ["English"],
                "public_projects": [{"id": project_id, "detail": "Built an ML dashboard"}],
            }
            for freelancer_id, project_id in (("f1", "p1"), ("f2", "p2"))
        ]
        review = MatchReview(action="accept", matches=[
            CandidateDecision(
                freelancer_id="f1", fit="strong",
                evidence=[EvidenceReference(source="p1", field="detail")],
            ),
            CandidateDecision(
                freelancer_id="f2", fit="strong",
                evidence=[EvidenceReference(source="p2", field="detail")],
            ),
        ])
        validate_review(review, candidates)
        self.assertEqual([match.freelancer_id for match in review.matches], ["f1"])

    def test_answer_shows_evidence_and_gap(self) -> None:
        search_plan = plan(professions=["Illustrator"])
        answer = render_recommendation(search_plan, [{
            "name": "Ari", "work_field": "Illustration", "fit": "partial",
            "match_evidence": [{"source_label": "Forest story", "quote": "watercolor scenes"}],
            "gaps": ["Confirm print-production experience"],
        }], search_plan.questions, "accepted")
        self.assertIn("watercolor scenes", answer)
        self.assertIn("Confirm print-production experience", answer)

    def test_selection_criteria_become_questions_when_model_omits_them(self) -> None:
        search_plan = plan(
            criteria_to_confirm=["project location", "budget range"],
            questions=[],
        )
        answer = render_recommendation(search_plan, [], [], "accepted")
        self.assertIn("Could you clarify project location?", answer)
        self.assertIn("Could you clarify budget range?", answer)


if __name__ == "__main__":
    unittest.main()
