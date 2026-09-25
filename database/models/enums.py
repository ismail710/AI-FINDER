"""Enumerations shared by the domain models."""

from enum import Enum


class UserRole(str, Enum):
    CLIENT = "client"
    FREELANCER = "freelancer"


class AvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class CompanySize(str, Enum):
    SOLO = "solo"
    SMALL = "small"
    MEDIUM = "medium"
    ENTERPRISE = "enterprise"


class RequestStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    MATCHING = "matching"
    SHORTLISTED = "shortlisted"
    STAFFED = "staffed"
    CLOSED = "closed"


class MatchRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EmbeddingSourceType(str, Enum):
    PROFILE = "profile"
    PROJECT = "project"
