"""Data models for AI analysis, vector retrieval, and matching."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from .enums import EmbeddingSourceType, MatchRunStatus
from .user import utc_now


@dataclass
class AIRequestAnalysis:
    id: str
    client_request_id: str
    raw_request: str
    problem_summary: str
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    work_field: str | None = None
    roles_needed: list[str] = field(default_factory=list)
    freelancers_needed: int = 1
    start_date: date | None = None
    deadline: date | None = None
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
    clarifying_questions: list[str] = field(default_factory=list)
    model_name: str = ""
    prompt_version: str = ""
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class FreelancerEmbedding:
    id: str
    freelancer_id: str
    source_type: EmbeddingSourceType
    source_id: str
    content: str
    embedding: list[float]
    embedding_model: str
    dimensions: int
    content_hash: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.dimensions != len(self.embedding):
            raise ValueError("Embedding dimensions must match the vector length.")


@dataclass
class AIMatchRun:
    id: str
    client_request_id: str
    analysis_id: str
    retrieval_method: str
    candidate_count: int
    status: MatchRunStatus = MatchRunStatus.PENDING
    model_name: str | None = None
    started_at: datetime = field(default_factory=utc_now)
    completed_at: datetime | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.candidate_count < 0:
            raise ValueError("Candidate count cannot be negative.")


@dataclass
class AIMatchResult:
    id: str
    match_run_id: str
    freelancer_id: str
    rank: int
    overall_score: Decimal
    skill_score: Decimal
    semantic_score: Decimal
    language_score: Decimal
    availability_score: Decimal
    budget_score: Decimal
    match_explanation: str
    proposed_role: str | None = None
    estimated_hours: Decimal | None = None
    estimated_cost_min: Decimal | None = None
    estimated_cost_max: Decimal | None = None
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if self.rank < 1:
            raise ValueError("Match rank must start at 1.")
        for score in (
            self.overall_score,
            self.skill_score,
            self.semantic_score,
            self.language_score,
            self.availability_score,
            self.budget_score,
        ):
            if not Decimal("0") <= score <= Decimal("100"):
                raise ValueError("Match scores must be between 0 and 100.")
