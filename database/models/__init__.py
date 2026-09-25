"""Public domain-model API."""

from .ai import AIRequestAnalysis, AIMatchResult, AIMatchRun, FreelancerEmbedding
from .client import Client
from .client_request import ClientRequest
from .enums import (
    AvailabilityStatus,
    CompanySize,
    EmbeddingSourceType,
    MatchRunStatus,
    RequestStatus,
    UserRole,
)
from .freelancer import Freelancer
from .project import Project
from .user import User

__all__ = [
    "AIRequestAnalysis",
    "AIMatchResult",
    "AIMatchRun",
    "AvailabilityStatus",
    "Client",
    "ClientRequest",
    "CompanySize",
    "EmbeddingSourceType",
    "Freelancer",
    "FreelancerEmbedding",
    "MatchRunStatus",
    "Project",
    "RequestStatus",
    "User",
    "UserRole",
]
