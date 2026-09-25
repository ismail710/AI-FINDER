"""Shared user model for client and freelancer accounts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from re import fullmatch

from .enums import UserRole


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass
class User:
    """Base account shared by every person who uses the platform."""

    id: str
    name: str
    email: str
    age: int | None = None
    photo: str | None = None
    is_verified: bool = False
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    role: UserRole = field(init=False)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("User id cannot be empty.")
        if not self.name.strip():
            raise ValueError("User name cannot be empty.")
        if not fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", self.email):
            raise ValueError("A valid email address is required.")
        if self.age is not None and not 18 <= self.age <= 120:
            raise ValueError("Age must be between 18 and 120.")

    def touch(self) -> None:
        """Mark the account as updated after a mutable field changes."""
        self.updated_at = utc_now()
