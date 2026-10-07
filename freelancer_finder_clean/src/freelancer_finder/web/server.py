"""Local browser UI for the freelancer matching and SQL agent.

Run with ``python -m freelancer_finder.web.server`` and ``PYTHONPATH=src``.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..config import DEFAULT_DATABASE_PATH, settings
from ..data.database import initialize_database
from ..data.memory import (
    conversation_id,
    load_constraints,
    load_messages,
    save_constraints,
    save_exchange,
)
from ..matching.search import verified_semantic_search


PAGE_PATH = Path(__file__).with_name("static") / "index.html"
MAX_REQUEST_BYTES = 131_072
logger = logging.getLogger("freelancer_finder.web")

# Memory endpoints may be requested as soon as the page loads, before the agent
# module is imported, so ensure the conversation tables already exist.
initialize_database()


def _optional_text(value: Any, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text.")
    return value.strip() or None


def _match_request(payload: dict[str, Any]) -> dict[str, object]:
    query = _optional_text(payload.get("query"), "query")
    if not query:
        raise ValueError("Enter a client request.")
    if len(query) > 2_000:
        raise ValueError("The client request must be 2,000 characters or fewer.")

    top = payload.get("top", 5)
    if isinstance(top, bool) or not isinstance(top, int) or not 1 <= top <= 20:
        raise ValueError("top must be a whole number from 1 to 20.")

    def rate_value(field: str) -> float | None:
        value = payload.get(field)
        if value in (None, ""):
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1_000_000:
            raise ValueError(f"{field} must be a nonnegative number.")
        return float(value)

    min_rate = rate_value("min_hourly_rate")
    max_rate = rate_value("max_hourly_rate")
    if min_rate is not None and max_rate is not None and min_rate > max_rate:
        raise ValueError("min_hourly_rate cannot exceed max_hourly_rate.")

    skills = payload.get("required_skills") or []
    if not isinstance(skills, list) or len(skills) > 20 or any(
        not isinstance(skill, str) or len(skill) > 100 for skill in skills
    ):
        raise ValueError("required_skills must be a list of at most 20 short skill names.")

    availability = _optional_text(payload.get("availability_status"), "availability_status")
    if availability not in (None, "available", "partial", "unavailable"):
        raise ValueError("availability_status must be available, partial, or unavailable.")
    currency = _optional_text(payload.get("currency"), "currency")
    if currency and min_rate is None and max_rate is None:
        raise ValueError("A currency requires a minimum or maximum hourly rate.")

    return verified_semantic_search(
        query,
        top=top,
        availability_status=availability,
        work_field=_optional_text(payload.get("work_field"), "work_field"),
        min_hourly_rate=min_rate,
        max_hourly_rate=max_rate,
        currency=currency,
        location=_optional_text(payload.get("location"), "location"),
        required_skills=[skill.strip() for skill in skills if skill.strip()],
    )


def _fixed_count_answer(question: str) -> dict[str, object] | None:
    # Handle straightforward counts with fixed SQL. A chat model can omit a
    # requested predicate, so these common checks should be deterministic.
    normalized = re.sub(r"[?.!]", "", question.casefold()).strip()
    status = None
    for pattern in (
        r"how many freelancers are (available|partial|unavailable)",
        r"how many (available|partial|unavailable) freelancers",
    ):
        match = re.fullmatch(pattern, normalized)
        if match:
            status = match.group(1)
            break
    if status:
        query = "SELECT COUNT(*) FROM freelancers WHERE availability_status = ?"
        with sqlite3.connect(DEFAULT_DATABASE_PATH) as connection:
            count = connection.execute(query, (status,)).fetchone()[0]
        return {"answer": f"There are {count} {status} freelancers.", "query": query, "parameters": [status], "source": "direct_sql"}
    if normalized in ("how many freelancers", "how many projects"):
        table = "freelancers" if normalized.endswith("freelancers") else "projects"
        query = f"SELECT COUNT(*) FROM {table}"
        with sqlite3.connect(DEFAULT_DATABASE_PATH) as connection:
            count = connection.execute(query).fetchone()[0]
        return {"answer": f"There are {count} {table}.", "query": query, "parameters": [], "source": "direct_sql"}
    return None


def _previous_question_answer(
    question: str, history: list[dict[str, str]]
) -> str | None:
    """Answer simple memory-recall requests without depending on an LLM."""
    normalized = re.sub(r"[^a-z0-9\s]", "", question.casefold())
    normalized = " ".join(normalized.split())
    asks_for_recall = any(
        re.fullmatch(pattern, normalized)
        for pattern in (
            r"what (?:was|is) my (?:previous|last) question",
            r"what did i ask (?:before|previously|last|last time)",
            r"(?:repeat|show me) my (?:previous|last) question",
            r"(?:list|show me) my (?:previous|earlier|last) questions",
        )
    )
    if not asks_for_recall:
        return None
    questions = [
        turn["content"] for turn in history if turn.get("role") == "user"
    ]
    if not questions:
        return "There is no previous question in this conversation yet."
    if "questions" in normalized:
        recent = questions[-5:]
        return "Your previous questions were:\n" + "\n".join(
            f"{index}. {content}" for index, content in enumerate(recent, start=1)
        )
    return f'Your previous question was: "{questions[-1]}"'


def _sql_request(payload: dict[str, Any]) -> dict[str, object]:
    question = _optional_text(payload.get("question"), "question")
    if not question:
        raise ValueError("Enter a database question.")
    if len(question) > 2_000:
        raise ValueError("The database question must be 2,000 characters or fewer.")
    fixed_answer = _fixed_count_answer(question)
    if fixed_answer:
        return fixed_answer

    # Import only when SQL mode is used; direct matching does not need an LLM.
    from ..agent.service import run_agent

    result = run_agent(question, mode="sql")
    content = result["messages"][-1].content
    return {"answer": content if isinstance(content, str) else json.dumps(content), "source": "agent_sql"}


def _chat_request(payload: dict[str, Any]) -> dict[str, object]:
    message = _optional_text(payload.get("message"), "message")
    if not message:
        raise ValueError("Enter a chat message.")
    if len(message) > 2_000:
        raise ValueError("Chat messages must be 2,000 characters or fewer.")
    # New clients send only a random conversation ID. The server owns the
    # authoritative history, which survives reloads and cannot be accidentally
    # duplicated by the browser. ``history`` remains a compatibility input for
    # callers making their first request without an ID.
    supplied_thread_id = payload.get("conversation_id")
    thread_id = conversation_id(supplied_thread_id)
    history = (
        load_messages(thread_id, limit=10)
        if supplied_thread_id not in (None, "")
        else payload.get("history", [])
    )
    if not isinstance(history, list) or len(history) > 10 or any(
        not isinstance(turn, dict)
        or turn.get("role") not in ("user", "assistant")
        or not isinstance(turn.get("content"), str)
        or not 0 < len(turn["content"]) <= (2_000 if turn["role"] == "user" else 8_000)
        for turn in history
    ):
        raise ValueError("history must contain at most 10 user/assistant messages.")

    remembered_answer = _previous_question_answer(message, history)
    if remembered_answer:
        save_exchange(thread_id, message, remembered_answer)
        return {
            "answer": remembered_answer,
            "conversation_id": thread_id,
            "route": "conversation",
            "tools_used": [],
            "matches": [],
            "verification_status": None,
            "constraint_notes": [],
            "review": {"outcome": "not_needed", "attempts": 0, "decisions": []},
            "search_plan": None,
            "searches": [],
        }

    fixed_answer = _fixed_count_answer(message)
    if fixed_answer:
        answer = str(fixed_answer["answer"])
        save_exchange(thread_id, message, answer)
        return {
            **fixed_answer,
            "route": "sql",
            "matches": [],
            "conversation_id": thread_id,
        }

    from ..agent.service import run_reviewed_agent

    confirmed_constraints = (
        load_constraints(thread_id)
        if supplied_thread_id not in (None, "")
        else []
    )
    result = run_reviewed_agent(
        message,
        mode="auto",
        history=history,
        confirmed_constraints=confirmed_constraints,
    )
    match_result: dict[str, object] | None = result.get("matching_result")
    tool_names: list[str] = ["semantic_freelancer_search"] if match_result and match_result.get("searches") else []
    for turn in result["messages"]:
        if turn.type == "ai":
            tool_names.extend(call["name"] for call in getattr(turn, "tool_calls", []))
        elif turn.type == "tool":
            try:
                candidate = json.loads(turn.content)
            except (TypeError, ValueError):
                continue
            if isinstance(candidate, dict) and "matches" in candidate and "status" in candidate:
                match_result = candidate

    content = result["messages"][-1].content
    answer = content if isinstance(content, str) else json.dumps(content)
    route = "semantic" if "semantic_freelancer_search" in tool_names else "sql" if tool_names else "conversation"
    response = {
        "answer": answer,
        "conversation_id": thread_id,
        "route": route,
        "tools_used": list(dict.fromkeys(tool_names)),
        "matches": match_result["matches"] if match_result else [],
        "verification_status": match_result["status"] if match_result else None,
        "constraint_notes": match_result.get("constraint_notes", []) if match_result else [],
        "review": result["review"],
        "search_plan": result.get("search_plan"),
        "searches": match_result.get("searches", []) if match_result else [],
    }
    search_plan = result.get("search_plan")
    if isinstance(search_plan, dict) and search_plan.get("route") == "match":
        save_constraints(thread_id, search_plan.get("hard_constraints", []))
    save_exchange(thread_id, message, answer)
    return response


def _conversation_request(thread_id: str) -> dict[str, object]:
    """Return stored messages so the browser can restore a local chat thread."""
    validated_id = conversation_id(thread_id)
    return {
        "conversation_id": validated_id,
        "messages": load_messages(validated_id, limit=50),
    }


def _status() -> dict[str, object]:
    counts = {"freelancers": 0, "embeddings": 0, "projects": 0}
    if DEFAULT_DATABASE_PATH.is_file():
        with sqlite3.connect(DEFAULT_DATABASE_PATH) as connection:
            for label, table in (
                ("freelancers", "freelancers"),
                ("embeddings", "freelancer_embeddings"),
                ("projects", "projects"),
            ):
                counts[label] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return {
        **counts,
        "embedding_model": settings.embedding_model,
        "token_configured": bool(
            settings.hf_token and settings.hf_token != "hf_your_token_here"
        ),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model_name,
        "sample_data": True,
    }


class WebHandler(BaseHTTPRequestHandler):
    def _json(self, status: HTTPStatus, data: dict[str, object]) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            encoded = PAGE_PATH.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        elif self.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
        elif self.path == "/api/status":
            try:
                self._json(HTTPStatus.OK, _status())
            except (OSError, sqlite3.Error) as error:
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
        elif match := re.fullmatch(
            r"/api/conversations/([A-Za-z0-9_-]{8,64})/messages", self.path
        ):
            try:
                self._json(HTTPStatus.OK, _conversation_request(match.group(1)))
            except (ValueError, OSError, sqlite3.Error) as error:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        if self.path not in ("/api/match", "/api/sql", "/api/chat"):
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_REQUEST_BYTES:
                raise ValueError("Request body is missing or too large.")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            if self.path == "/api/match":
                result = _match_request(payload)
            elif self.path == "/api/sql":
                result = _sql_request(payload)
            else:
                result = _chat_request(payload)
            self._json(HTTPStatus.OK, result)
        except (ValueError, json.JSONDecodeError) as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:
            logger.exception("Request failed")
            details = str(error)
            if "402 Payment Required" in details or "depleted your monthly included credits" in details:
                details = (
                    "Hugging Face Inference Providers credits are exhausted. "
                    "Restore provider access and try again."
                )
            self._json(HTTPStatus.BAD_GATEWAY, {"error": details})

    def log_message(self, format: str, *args: object) -> None:
        logger.info("%s %s", self.address_string(), format % args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local freelancer test page.")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    server = ThreadingHTTPServer(("127.0.0.1", arguments.port), WebHandler)
    print(f"Freelancer test page: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
