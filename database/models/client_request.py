"""Client request model for work the client wants staffed."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from .enums import RequestStatus
from .user import utc_now


@dataclass
class ClientRequest:
    id: str
    client_id: str
    title: str
    raw_request: str
    required_skills: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    work_field: str | None = None
    freelancers_needed: int = 1
    start_date: date | None = None
    deadline: date | None = None
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None
    currency: str | None = None
    status: RequestStatus = RequestStatus.DRAFT
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.client_id.strip():
            raise ValueError("Request id and client id are required.")
        if not self.title.strip() or not self.raw_request.strip():
            raise ValueError("Request title and details are required.")
        if self.freelancers_needed < 1:
            raise ValueError("At least one freelancer must be requested.")
        if self.budget_min is not None and self.budget_min < 0:
            raise ValueError("Minimum budget cannot be negative.")
        if self.budget_max is not None and self.budget_max < 0:
            raise ValueError("Maximum budget cannot be negative.")
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("Minimum budget cannot exceed maximum budget.")

    def touch(self) -> None:
        self.updated_at = utc_now()
