"""Client account model."""

from __future__ import annotations

from dataclasses import dataclass, field

from .enums import CompanySize, UserRole
from .user import User


@dataclass
class Client(User):
    """A user who submits requests for freelance talent."""

    phone: str | None = None
    company_name: str | None = None
    job_title: str | None = None
    company_website: str | None = None
    industry: str | None = None
    company_size: CompanySize | None = None
    location: str | None = None
    timezone: str | None = None
    languages: list[str] = field(default_factory=list)
    bio: str = ""
    request_ids: list[str] = field(default_factory=list)
    role: UserRole = field(default=UserRole.CLIENT, init=False)

    def add_request(self, request_id: str) -> None:
        """Attach a client request reference without creating duplicates."""
        if request_id and request_id not in self.request_ids:
            self.request_ids.append(request_id)
            self.touch()
