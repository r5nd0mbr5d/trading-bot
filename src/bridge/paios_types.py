"""Shared session types mirroring the PAIOS SessionType definitions.

These types enable the trading-bot to participate in PAIOS-orchestrated
session handoffs and agent topology workflows.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SessionType(str, Enum):
    """Trading-bot session types, mirroring PAIOS SessionType enum."""

    IMPL = "impl"
    ARCH = "arch"
    RSRCH = "rsrch"
    OPS = "ops"
    DEBUG = "debug"
    REVIEW = "review"


@dataclass
class HandoffPacket:
    """Structured handoff model for passing context between sessions.

    Parameters
    ----------
    source_session_type : SessionType
        The session type that is handing off.
    target_session_type : SessionType
        The session type that should receive the handoff.
    summary : str
        Human-readable summary of what was accomplished and what remains.
    context_files : list[str]
        Repository-relative paths the target session should pre-read.
    parent_job_id : str | None
        Optional job ID from the PAIOS orchestrator.
    metadata : dict[str, Any]
        Arbitrary additional context (e.g. step number, strategy name).
    """

    source_session_type: SessionType
    target_session_type: SessionType
    summary: str
    context_files: list[str]
    parent_job_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the packet to a JSON-compatible dictionary.

        Returns
        -------
        dict[str, Any]
            All fields serialized with enum values as plain strings.
        """
        return {
            "source_session_type": self.source_session_type.value,
            "target_session_type": self.target_session_type.value,
            "summary": self.summary,
            "context_files": self.context_files,
            "parent_job_id": self.parent_job_id,
            "metadata": self.metadata,
        }


@dataclass
class SessionConfig:
    """Configuration for a single session type.

    Parameters
    ----------
    type : SessionType
        The session type this config applies to.
    pre_reads : list[str]
        Repository-relative file paths the agent should load at session start.
    scope_guard : dict[str, bool]
        Allowed/prohibited actions keyed by action name.
    description : str
        Short human-readable description of this session type's purpose.
    """

    type: SessionType
    pre_reads: list[str]
    scope_guard: dict[str, bool]
    description: str
