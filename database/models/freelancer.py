"""Freelancer account model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .enums import AvailabilityStatus, UserRole
from .user import User


@dataclass
class Freelancer(User):
    """A user who provides freelance services and portfolio projects."""

    bio: str = ""
    portfolio: str | None = None
    interests: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    work_field: str = ""
    experience_years: int | None = None
    location: str | None = None
    timezone: str | None = None
    hourly_rate: Decimal | None = None
    currency: str | None = None
    availability_status: AvailabilityStatus = AvailabilityStatus.UNAVAILABLE
    available_from: date | None = None
    weekly_capacity_hours: int | None = None
    project_ids: list[str] = field(default_factory=list)
    role: UserRole = field(default=UserRole.FREELANCER, init=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.experience_years is not None and self.experience_years < 0:
            raise ValueError("Experience years cannot be negative.")
        if self.hourly_rate is not None and self.hourly_rate < 0:
            raise ValueError("Hourly rate cannot be negative.")
        if self.weekly_capacity_hours is not None and not 0 <= self.weekly_capacity_hours <= 168:
            raise ValueError("Weekly capacity must be between 0 and 168 hours.")
        if self.hourly_rate is not None and not self.currency:
            raise ValueError("Currency is required when an hourly rate is set.")

    def add_project(self, project_id: str) -> None:
        """Attach a project reference without creating duplicates."""
        if project_id and project_id not in self.project_ids:
            self.project_ids.append(project_id)
            self.touch()
