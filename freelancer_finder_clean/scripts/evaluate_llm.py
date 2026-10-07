r"""Evaluate planner and matching behavior against realistic client conversations.

From the project root on Windows CMD:
    set PYTHONPATH=%CD%\src
    python scripts\evaluate_llm.py
    python scripts\evaluate_llm.py --full
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from freelancer_finder.agent.service import planner_model, review_model
from freelancer_finder.matching.planner import create_search_plan
from freelancer_finder.matching.review import run_matching_workflow
from freelancer_finder.matching.search import database_catalog


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = PROJECT_ROOT / "evaluation" / "client_conversations.json"


def _contains_expected_term(plan: dict[str, Any], expected: list[str]) -> bool:
    if not expected:
        return True
    searchable = " ".join(
        [
            *plan.get("professions", []),
            *plan.get("suggested_skills", []),
            plan.get("search_query", ""),
        ]
    ).casefold()
    return any(term.casefold() in searchable for term in expected)


def evaluate_case(case: dict[str, Any], *, full: bool) -> dict[str, Any]:
    started = time.perf_counter()
    history = case.get("history", [])
    confirmed = case.get("confirmed_constraints", [])
    result: dict[str, Any] = {
        "id": case["id"],
        "language": case["language"],
        "valid_json": False,
        "route_correct": False,
        "intent_terms_found": False,
        "constraints_correct": False,
        "full_status_correct": None,
    }
    try:
        plan = create_search_plan(
            planner_model,
            case["question"],
            history,
            database_catalog(),
            confirmed_constraints=confirmed,
        )
        dumped = plan.model_dump()
        result["valid_json"] = True
        result["route"] = plan.route
        result["route_correct"] = plan.route == case["expected_route"]
        result["intent_terms_found"] = _contains_expected_term(
            dumped, case.get("expected_terms_any", [])
        )
        actual_fields = {item["field"] for item in dumped["hard_constraints"]}
        expected_fields = set(case.get("expected_constraint_fields", []))
        result["constraint_fields"] = sorted(actual_fields)
        result["constraints_correct"] = actual_fields == expected_fields

        if full and plan.route == "match":
            user_messages = [
                str(item["source_quote"]) for item in confirmed
            ] + [
                turn["content"] for turn in history if turn["role"] == "user"
            ] + [case["question"]]
            matched = run_matching_workflow(
                review_model, plan, user_messages
            )
            result["full_status"] = matched["status"]
            expected_status = case.get("expected_full_status")
            result["full_status_correct"] = (
                None if expected_status is None else matched["status"] == expected_status
            )
    except Exception as error:
        result["error"] = str(error)[:500]
    result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    return result


def percentage(results: list[dict[str, Any]], field: str) -> float:
    applicable = [item[field] for item in results if item.get(field) is not None]
    return round(100 * sum(bool(value) for value in applicable) / len(applicable), 1) if applicable else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also run semantic retrieval and evidence review (slower and uses embeddings).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the detailed JSON results.",
    )
    arguments = parser.parse_args()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    results = [evaluate_case(case, full=arguments.full) for case in cases]
    durations = [item["elapsed_seconds"] for item in results]
    summary = {
        "cases": len(results),
        "valid_json_percent": percentage(results, "valid_json"),
        "route_accuracy_percent": percentage(results, "route_correct"),
        "intent_term_accuracy_percent": percentage(results, "intent_terms_found"),
        "constraint_accuracy_percent": percentage(results, "constraints_correct"),
        "no_fit_accuracy_percent": percentage(results, "full_status_correct"),
        "median_seconds": round(statistics.median(durations), 3),
        "slowest_seconds": round(max(durations), 3),
    }
    for item in results:
        checks = " ".join(
            f"{name}={'ok' if item.get(name) else 'FAIL'}"
            for name in ("valid_json", "route_correct", "intent_terms_found", "constraints_correct")
        )
        print(f"{item['id']}: {checks} time={item['elapsed_seconds']}s")
        if item.get("error"):
            print(f"  error: {item['error']}")
    print(json.dumps(summary, indent=2))
    if arguments.output:
        arguments.output.write_text(
            json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
