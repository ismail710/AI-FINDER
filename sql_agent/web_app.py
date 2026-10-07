"""Local browser UI for the freelancer matching and SQL agent.

Run from the repository root with ``python -m sql_agent.web_app``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .database import DEFAULT_DATABASE_PATH
from .embed_projects import EMBEDDING_MODEL
from .match_freelancers import verified_semantic_search


PAGE_PATH = Path(__file__).with_name("web.html")
MAX_REQUEST_BYTES = 131_072
logger = logging.getLogger("sql_agent.web")


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

    rate = payload.get("max_hourly_rate")
    if rate in (None, ""):
        rate = None
    elif isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 <= rate <= 1_000_000:
        raise ValueError("max_hourly_rate must be a nonnegative number.")

    skills = payload.get("required_skills") or []
    if not isinstance(skills, list) or len(skills) > 20 or any(
        not isinstance(skill, str) or len(skill) > 100 for skill in skills
    ):
        raise ValueError("required_skills must be a list of at most 20 short skill names.")

    availability = _optional_text(payload.get("availability_status"), "availability_status")
    if availability not in (None, "available", "partial", "unavailable"):
        raise ValueError("availability_status must be available, partial, or unavailable.")
    currency = _optional_text(payload.get("currency"), "currency")
    if currency and rate is None:
        raise ValueError("A currency requires a maximum hourly rate.")

    return verified_semantic_search(
        query,
        top=top,
        availability_status=availability,
        work_field=_optional_text(payload.get("work_field"), "work_field"),
        max_hourly_rate=rate,
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


def _sql_request(payload: dict[str, Any]) -> dict[str, object]:
    question = _optional_text(payload.get("question"), "question")
    if not question:
        raise ValueError("Enter a database question.")
    if len(question) > 2_000:
        raise ValueError("The database question must be 2,000 characters or fewer.")
    fixed_answer = _fixed_count_answer(question)
    if fixed_answer:
        return fixed_answer

    # Import only when SQL mode is used; matching does not need a chat model.
    load_dotenv(DEFAULT_DATABASE_PATH.parent / ".env")
    from .agent import run_agent

    result = run_agent(question, mode="sql")
    content = result["messages"][-1].content
    return {"answer": content if isinstance(content, str) else json.dumps(content), "source": "sql_agent"}


def _chat_request(payload: dict[str, Any]) -> dict[str, object]:
    message = _optional_text(payload.get("message"), "message")
    if not message:
        raise ValueError("Enter a chat message.")
    if len(message) > 2_000:
        raise ValueError("Chat messages must be 2,000 characters or fewer.")
    history = payload.get("history", [])
    if not isinstance(history, list) or len(history) > 10 or any(
        not isinstance(turn, dict)
        or turn.get("role") not in ("user", "assistant")
        or not isinstance(turn.get("content"), str)
        or not 0 < len(turn["content"]) <= (2_000 if turn["role"] == "user" else 8_000)
        for turn in history
    ):
        raise ValueError("history must contain at most 10 user/assistant messages.")

    fixed_answer = _fixed_count_answer(message)
    if fixed_answer:
        return {**fixed_answer, "route": "sql", "matches": []}

    load_dotenv(DEFAULT_DATABASE_PATH.parent / ".env")
    from .agent import run_reviewed_agent

    result = run_reviewed_agent(message, mode="auto", history=history)
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
    return {
        "answer": answer,
        "route": route,
        "tools_used": list(dict.fromkeys(tool_names)),
        "matches": match_result["matches"] if match_result else [],
        "verification_status": match_result["status"] if match_result else None,
        "constraint_notes": match_result.get("constraint_notes", []) if match_result else [],
        "review": result["review"],
        "search_plan": result.get("search_plan"),
        "searches": match_result.get("searches", []) if match_result else [],
    }


def _status() -> dict[str, object]:
    load_dotenv(DEFAULT_DATABASE_PATH.parent / ".env")
    counts = {"freelancers": 0, "embeddings": 0, "projects": 0}
    if DEFAULT_DATABASE_PATH.is_file():
        with sqlite3.connect(DEFAULT_DATABASE_PATH) as connection:
            for label, table in (
                ("freelancers", "freelancers"),
                ("embeddings", "freelancer_embeddings"),
                ("projects", "projects"),
            ):
                counts[label] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    token = os.environ.get("HF_TOKEN", "")
    llm_provider = os.environ.get("LLM_PROVIDER", "huggingface").casefold()
    llm_model = (
        os.environ.get("OLLAMA_MODEL", "qwen3:4b")
        if llm_provider == "ollama"
        else os.environ.get("HF_MODEL", "Qwen/Qwen3.8-27B")
    )
    return {
        **counts,
        "embedding_model": EMBEDDING_MODEL,
        "token_configured": bool(token and token != "hf_your_token_here"),
        "llm_provider": llm_provider,
        "llm_model": llm_model,
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
