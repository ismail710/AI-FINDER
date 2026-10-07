"""Behavior checks for the bounded LLM answer review loop."""

from __future__ import annotations

import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


agent_module = importlib.import_module("freelancer_finder.agent.service")


def ai_message(content: str) -> SimpleNamespace:
    return SimpleNamespace(type="ai", content=content, tool_calls=[])


class ReviewLoopTests(unittest.TestCase):
    def test_accepted_answer_does_not_retry(self) -> None:
        initial = {"messages": [ai_message("Grounded answer")]}
        verdict = {"action": "accept", "tool": "none", "feedback": ""}
        with (
            patch.object(agent_module, "run_agent", return_value=initial),
            patch.object(agent_module, "_review_answer", return_value=verdict),
            patch.object(agent_module, "agent") as fake_agent,
        ):
            result = agent_module.run_reviewed_agent("Find a developer", mode="sql")
        fake_agent.invoke.assert_not_called()
        self.assertEqual(result["review"]["outcome"], "accepted")
        self.assertEqual(result["review"]["attempts"], 1)

    def test_weak_answer_triggers_one_retry(self) -> None:
        first = ai_message("Unclear answer")
        initial = {"messages": [first]}
        revised = {"messages": [first, ai_message("Clear answer with evidence")]}
        decisions = [
            {"action": "retry", "tool": "sql", "feedback": "Check the candidate evidence."},
            {"action": "accept", "tool": "none", "feedback": ""},
        ]
        with (
            patch.object(agent_module, "run_agent", return_value=initial),
            patch.object(agent_module, "_review_answer", side_effect=decisions),
            patch.object(agent_module, "sql_only_agent", new=Mock(invoke=Mock(return_value=revised))) as fake_agent,
        ):
            result = agent_module.run_reviewed_agent("Find a developer", mode="sql")
        fake_agent.invoke.assert_called_once()
        self.assertEqual(result["messages"][-1].content, "Clear answer with evidence")
        self.assertEqual(result["review"]["outcome"], "accepted")
        self.assertEqual(result["review"]["attempts"], 2)

    def test_wording_issue_rewrites_without_tools(self) -> None:
        initial = {"messages": [ai_message("Vague answer")]}
        decisions = [
            {"action": "retry", "tool": "none", "feedback": "State the result clearly."},
            {"action": "accept", "tool": "none", "feedback": ""},
        ]
        with (
            patch.object(agent_module, "run_agent", return_value=initial),
            patch.object(agent_module, "_review_answer", side_effect=decisions),
            patch.object(agent_module, "review_model", new=Mock(invoke=Mock(return_value=ai_message("Clear answer")))),
            patch.object(agent_module, "agent") as fake_agent,
        ):
            result = agent_module.run_reviewed_agent("Find a developer", mode="sql")
        fake_agent.invoke.assert_not_called()
        self.assertEqual(result["messages"][-1].content, "Clear answer")
        self.assertEqual(result["review"]["attempts"], 2)

    def test_retry_limit_hides_rejected_answer(self) -> None:
        initial = {"messages": [ai_message("Best available answer")]}
        verdict = {"action": "retry", "tool": "sql", "feedback": "Check again."}
        with (
            patch.object(agent_module, "run_agent", return_value=initial),
            patch.object(agent_module, "_review_answer", return_value=verdict),
            patch.object(agent_module, "AGENT_REVIEW_MAX_RETRIES", 0),
            patch.object(agent_module, "agent") as fake_agent,
        ):
            result = agent_module.run_reviewed_agent("How many freelancers?", mode="sql")
        fake_agent.invoke.assert_not_called()
        self.assertIn("couldn't verify a reliable answer", result["messages"][-1].content)
        self.assertEqual(result["review"]["outcome"], "retry_limit")

    def test_failed_retry_hides_rejected_answer(self) -> None:
        initial = {"messages": [ai_message("Wrong answer")]}
        verdict = {"action": "retry", "tool": "sql", "feedback": "Check the count."}
        with (
            patch.object(agent_module, "run_agent", return_value=initial),
            patch.object(agent_module, "_review_answer", return_value=verdict),
            patch.object(agent_module, "sql_only_agent", new=Mock(invoke=Mock(side_effect=RuntimeError("provider unavailable")))),
        ):
            result = agent_module.run_reviewed_agent("How many freelancers?", mode="sql")
        self.assertIn("couldn't verify a reliable answer", result["messages"][-1].content)
        self.assertNotIn("Wrong answer", result["messages"][-1].content)
        self.assertEqual(result["review"]["outcome"], "retry_failed")


if __name__ == "__main__":
    unittest.main()
