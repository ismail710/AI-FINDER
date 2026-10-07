"""Validation checks for the domain-neutral matching workflow."""

from __future__ import annotations

import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch

from freelancer_finder.matching.review import (
    CandidateDecision,
    EvidenceReference,
    MatchReview,
    diverse_candidates,
    normalize_profile_only_strong_matches,
    relaxed_constraint_gap,
    render_recommendation,
    remove_verified_constraint_gaps,
    validate_review,
)
from freelancer_finder.matching.planner import (
    HardConstraint,
    SearchPlan,
    apply_latest_availability,
    apply_latest_rate_correction,
    constraint_arguments,
    complete_explicit_hourly_currency,
    complete_explicit_skill_constraints,
    create_search_plan,
    merge_confirmed_constraints,
    remove_satisfied_followups,
    remove_unknown_work_field,
    structured_response,
)
from freelancer_finder.matching.search import (
    _project_relevance_score,
    adaptive_verified_semantic_search,
    constraint_relaxation_variants,
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
    def test_relaxation_variants_change_only_one_constraint(self) -> None:
        constraints = {
            "availability_status": "available",
            "max_hourly_rate": 60,
            "currency": "USD",
            "required_skills": ["Python", "Django"],
        }

        variants = constraint_relaxation_variants(constraints)

        self.assertEqual(variants[0][1]["field"], "availability_status")
        self.assertEqual(variants[0][1]["applied_value"], "partial")
        rate_variant = next(
            filters
            for filters, change in variants
            if change["field"] == "max_hourly_rate"
        )
        self.assertNotIn("max_hourly_rate", rate_variant)
        self.assertEqual(rate_variant["availability_status"], "available")
        django_variant = next(
            filters
            for filters, change in variants
            if change["field"] == "required_skills"
            and change["original_value"] == "Django"
        )
        self.assertEqual(django_variant["required_skills"], ["Python"])
        self.assertEqual(django_variant["currency"], "USD")

    def test_adaptive_search_uses_first_successful_single_relaxation(self) -> None:
        ranked = [{
            "freelancer_id": "f1",
            "name": "Amina",
            "work_field": "Software development",
            "location": "Lisbon, Portugal",
            "skills": ["Python", "Django"],
            "hourly_rate": 40,
            "currency": "USD",
            "availability_status": "available",
            "sample_project": "Customer Portal",
            "profile_score": 0.7,
            "project_score": 0.8,
            "combined_score": 0.75,
        }]

        def verify(_ids, **filters):
            if (
                filters.get("availability_status") == "available"
                and filters.get("max_hourly_rate") is None
            ):
                return [{
                    "freelancer_id": "f1",
                    "name": "Amina",
                    "work_field": "Software development",
                    "location": "Lisbon, Portugal",
                    "skills_json": '["Python", "Django"]',
                    "hourly_rate": 40,
                    "currency": "USD",
                    "availability_status": "available",
                }]
            return []

        with (
            patch("freelancer_finder.matching.search.match_freelancers", return_value=ranked) as rank,
            patch("freelancer_finder.matching.search.verify_candidate_batch", side_effect=verify),
        ):
            result = adaptive_verified_semantic_search(
                "Django developer",
                top=3,
                availability_status="available",
                max_hourly_rate=30,
                currency="USD",
            )

        rank.assert_called_once()
        self.assertEqual(result["status"], "relaxed")
        self.assertEqual(result["relaxed_constraints"][0]["field"], "max_hourly_rate")
        self.assertNotIn("max_hourly_rate", result["applied_constraints"])
        self.assertEqual(result["applied_constraints"]["availability_status"], "available")
        self.assertEqual(result["matches"][0]["freelancer_id"], "f1")

    def test_relaxed_rate_gap_shows_candidate_actual_rate(self) -> None:
        gap = relaxed_constraint_gap(
            {"field": "max_hourly_rate", "original_value": 30},
            {"currency": "USD", "hourly_rate": 40},
        )

        self.assertIn("maximum hourly rate was 30", gap)
        self.assertIn("USD 40/hour", gap)

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

    def test_confirmed_constraint_is_carried_when_model_omits_it(self) -> None:
        search_plan = plan()

        merge_confirmed_constraints(
            search_plan,
            [{"field": "location", "value": "Portugal", "source_quote": "in Portugal"}],
        )

        self.assertEqual(
            constraint_arguments(search_plan, ["in Portugal", "Show me more options"]),
            {"location": "Portugal"},
        )

    def test_explicitly_removed_confirmed_constraint_is_not_carried(self) -> None:
        search_plan = plan(removed_constraints=["location"])

        merge_confirmed_constraints(
            search_plan,
            [{"field": "location", "value": "Portugal", "source_quote": "in Portugal"}],
        )

        self.assertEqual(search_plan.hard_constraints, [])

    def test_project_evidence_score_prefers_query_relevance_over_recency(self) -> None:
        relevant = {
            "title": "Django booking portal",
            "detail": "Implemented appointments and PostgreSQL persistence",
            "work_field": "Software development",
            "skills": ["Python", "Django", "PostgreSQL"],
            "role": "Backend developer",
            "client_industry": "Healthcare",
        }
        unrelated = {
            "title": "Brand campaign",
            "detail": "Created social media assets",
            "work_field": "Marketing",
            "skills": ["Copywriting"],
            "role": "Marketer",
            "client_industry": "Retail",
        }

        self.assertGreater(
            _project_relevance_score(relevant, "Python Django booking developer"),
            _project_relevance_score(unrelated, "Python Django booking developer"),
        )

    def test_explicit_mandatory_skill_is_a_hard_constraint(self) -> None:
        search_plan = plan(hard_constraints=[HardConstraint(
            field="required_skills", value=["Python"], source_quote="must know Python"
        )])
        self.assertEqual(
            constraint_arguments(search_plan, ["The freelancer must know Python"]),
            {"required_skills": ["Python"]},
        )

    def test_natural_with_skills_phrase_is_a_hard_constraint(self) -> None:
        request = (
            "Find me an available Python developer with Django skills "
            "under 60 USD per hour."
        )
        search_plan = plan(hard_constraints=[
            HardConstraint(
                field="availability_status",
                value="available",
                source_quote="available",
            ),
            HardConstraint(
                field="required_skills",
                value=["Django"],
                source_quote="with Django skills",
            ),
            HardConstraint(
                field="max_hourly_rate",
                value=60,
                source_quote="under 60 USD per hour",
            ),
            HardConstraint(
                field="currency",
                value="USD",
                source_quote="under 60 USD per hour",
            ),
        ])

        self.assertEqual(
            constraint_arguments(search_plan, [request]),
            {
                "availability_status": "available",
                "required_skills": ["Django"],
                "max_hourly_rate": 60,
                "currency": "USD",
            },
        )

    def test_omitted_named_skill_constraint_is_recovered_from_user_text(self) -> None:
        request = "Find a developer with Python and Django skills"
        search_plan = plan()

        complete_explicit_skill_constraints(search_plan, [request])

        self.assertEqual(
            constraint_arguments(search_plan, [request]),
            {"required_skills": ["Python", "Django"]},
        )

    def test_project_theme_does_not_become_a_skill_constraint(self) -> None:
        request = "Build a web app with AI assistance"
        search_plan = plan()

        complete_explicit_skill_constraints(search_plan, [request])

        self.assertEqual(constraint_arguments(search_plan, [request]), {})

    def test_inferred_skill_cannot_become_a_hard_constraint(self) -> None:
        search_plan = plan(hard_constraints=[HardConstraint(
            field="required_skills", value=["Python"], source_quote="build a data product"
        )])
        with self.assertRaisesRegex(ValueError, "explicit skill wording"):
            constraint_arguments(search_plan, ["Help me build a data product"])

    def test_currency_is_recovered_only_from_explicit_hourly_quote(self) -> None:
        search_plan = plan(hard_constraints=[HardConstraint(
            field="max_hourly_rate",
            value=60,
            source_quote="under 60 USD per hour",
        )])

        complete_explicit_hourly_currency(search_plan)

        self.assertEqual(
            constraint_arguments(
                search_plan,
                ["Find a developer under 60 USD per hour"],
            ),
            {"max_hourly_rate": 60, "currency": "USD"},
        )

    def test_ambiguous_hourly_currency_is_not_guessed(self) -> None:
        search_plan = plan(hard_constraints=[HardConstraint(
            field="max_hourly_rate",
            value=60,
            source_quote="under $60 per hour",
        )])

        complete_explicit_hourly_currency(search_plan)

        with self.assertRaisesRegex(ValueError, "explicit currency"):
            constraint_arguments(search_plan, ["Find a developer under $60 per hour"])

    def test_verified_constraints_are_not_asked_again(self) -> None:
        search_plan = plan(
            criteria_to_confirm=[
                "Availability status confirmed as available",
                "Hourly rate confirmed under 60 USD",
                "Communication style",
            ],
            questions=[
                "Are they available?",
                "What communication cadence do you prefer?",
            ],
        )

        remove_satisfied_followups(
            search_plan,
            {
                "availability_status": "available",
                "max_hourly_rate": 60,
                "currency": "USD",
            },
        )

        self.assertEqual(search_plan.criteria_to_confirm, ["Communication style"])
        self.assertEqual(
            search_plan.questions,
            ["What communication cadence do you prefer?"],
        )

    def test_total_budget_cannot_become_hourly_ceiling(self) -> None:
        search_plan = plan(hard_constraints=[
            HardConstraint(field="max_hourly_rate", value=5000, source_quote="budget is 5000 USD"),
            HardConstraint(field="currency", value="USD", source_quote="budget is 5000 USD"),
        ])
        with self.assertRaisesRegex(ValueError, "total budget"):
            constraint_arguments(search_plan, ["My budget is 5000 USD"])

    def test_latest_followup_replaces_maximum_with_minimum_rate(self) -> None:
        first = (
            "Find me an available Python developer with Django skills "
            "under 60 USD per hour."
        )
        correction = "give me one with more 60 dollars"
        search_plan = plan(
            goal=first,
            search_query="Python Django developer under 60 USD per hour",
            hard_constraints=[
                HardConstraint(
                    field="availability_status",
                    value="available",
                    source_quote="available",
                ),
                HardConstraint(
                    field="required_skills",
                    value=["Django"],
                    source_quote="with Django skills",
                ),
                HardConstraint(
                    field="max_hourly_rate",
                    value=60,
                    source_quote="under 60 USD per hour",
                ),
                HardConstraint(
                    field="currency",
                    value="USD",
                    source_quote="under 60 USD per hour",
                ),
            ],
        )

        apply_latest_rate_correction(search_plan, [first, correction])
        constraints = constraint_arguments(search_plan, [first, correction])

        self.assertNotIn("max_hourly_rate", constraints)
        self.assertEqual(constraints["min_hourly_rate"], 60)
        self.assertEqual(constraints["currency"], "USD")
        self.assertEqual(constraints["availability_status"], "available")
        self.assertEqual(constraints["required_skills"], ["Django"])
        self.assertNotIn("under 60", search_plan.goal.casefold())
        self.assertIn("minimum hourly rate", search_plan.goal.casefold())

        apply_latest_rate_correction(search_plan, [first, correction])
        self.assertEqual(
            search_plan.goal.casefold().count("minimum hourly rate"),
            1,
        )

    def test_explicit_availability_is_preserved_when_model_omits_it(self) -> None:
        request = "Find an available Python developer"
        search_plan = plan()

        apply_latest_availability(search_plan, [request])

        self.assertEqual(
            constraint_arguments(search_plan, [request]),
            {"availability_status": "available"},
        )

    def test_profession_is_not_used_as_unknown_exact_work_field(self) -> None:
        search_plan = plan(hard_constraints=[HardConstraint(
            field="work_field",
            value="Python developer",
            source_quote="Python developer",
        )])

        remove_unknown_work_field(
            search_plan,
            {
                "work_fields": [
                    {"work_field": "Software development", "count": 10}
                ]
            },
        )

        self.assertEqual(search_plan.hard_constraints, [])

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

    def test_profile_only_strong_fit_is_normalized_for_live_workflow(self) -> None:
        review = MatchReview(action="accept", matches=[CandidateDecision(
            freelancer_id="f1",
            fit="strong",
            evidence=[EvidenceReference(source="profile", field="skills")],
        )])

        normalize_profile_only_strong_matches(review)

        self.assertEqual(review.matches[0].fit, "partial")
        self.assertEqual(
            review.matches[0].gaps,
            ["Confirm comparable public-project outcomes"],
        )

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

    def test_sql_verified_rate_is_not_reported_as_an_evidence_gap(self) -> None:
        review = MatchReview(action="accept", matches=[CandidateDecision(
            freelancer_id="f1",
            fit="partial",
            evidence=[EvidenceReference(source="profile", field="skills")],
            gaps=["No public evidence of hourly rate above 60 USD"],
        )])

        remove_verified_constraint_gaps(
            review,
            {"min_hourly_rate": 60, "currency": "USD"},
        )

        self.assertEqual(
            review.matches[0].gaps,
            ["Confirm comparable public-project outcomes"],
        )


if __name__ == "__main__":
    unittest.main()
