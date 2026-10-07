"""Central configuration for the application.

Every module imports ``settings`` from here instead of reading environment
variables independently.  This keeps paths and provider selection predictable
for the web server, CLI, scripts, and tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from os import environ
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_DATABASE_PATH = DATA_DIR / "freelancer.sqlite3"
SCHEMA_PATH = DATA_DIR / "schema.sql"

load_dotenv(ENV_PATH)


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = int(environ.get(name, str(default)))
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class Settings:
    """Typed runtime settings loaded once from ``.env`` and the process."""

    database_path: Path = DEFAULT_DATABASE_PATH
    embedding_model: str = environ.get(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    hf_token: str | None = environ.get("HF_TOKEN")
    llm_provider: str = environ.get("LLM_PROVIDER", "ollama").casefold()
    hf_model: str = environ.get("HF_MODEL", "Qwen/Qwen3.8-27B")
    ollama_model: str = environ.get("OLLAMA_MODEL", "qwen3:4b")
    ollama_base_url: str = environ.get(
        "OLLAMA_BASE_URL", "http://127.0.0.1:11435"
    ).rstrip("/").removesuffix("/v1")
    ollama_timeout_seconds: int = int(environ.get("OLLAMA_TIMEOUT_SECONDS", "180"))
    hf_timeout_seconds: int = int(environ.get("HF_TIMEOUT_SECONDS", "90"))
    max_output_tokens: int = int(environ.get("HF_MAX_OUTPUT_TOKENS", "2048"))
    planner_output_tokens: int = _bounded_int(
        "PLANNER_MAX_OUTPUT_TOKENS", 768, 256, 4096
    )
    review_output_tokens: int = _bounded_int(
        "REVIEW_MAX_OUTPUT_TOKENS", 1024, 256, 4096
    )
    recursion_limit: int = int(environ.get("HF_RECURSION_LIMIT", "12"))
    review_max_retries: int = _bounded_int("HF_REVIEW_MAX_RETRIES", 2, 0, 3)

    @property
    def llm_model_name(self) -> str:
        return self.ollama_model if self.llm_provider == "ollama" else self.hf_model


settings = Settings()
