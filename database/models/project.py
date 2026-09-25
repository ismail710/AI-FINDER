"""Freelancer portfolio project model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from .user import utc_now


@dataclass
class Project:
    id: str
    freelancer_id: str
    title: str
    detail: str
    photos: list[str] = field(default_factory=list)
    project_url: str | None = None
    work_field: str = ""
    skills_used: list[str] = field(default_factory=list)
    role: str | None = None
    client_industry: str | None = None
    completed_at: date | None = None
    is_public: bool = True
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.freelancer_id.strip():
            raise ValueError("Project id and freelancer id are required.")
        if not self.title.strip() or not self.detail.strip():
            raise ValueError("Project title and detail are required.")
