"""The invocation contract between HWD-ZERO and this agent.

ZERO writes one JSON object to stdin and reads the last JSON object printed to
stdout. Anything else on stdout — logs, warnings, a library's chatter — is
ignored, which is what lets an existing repository become an agent without
silencing its logging.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Invocation:
    """What ZERO asked for."""

    mission_id: str = ""
    agent_id: str = "lead_scraper"
    action: str = "health"
    payload: dict[str, Any] = field(default_factory=dict)
    mission_workspace: str = ""

    @classmethod
    def from_json(cls, raw: str) -> Invocation:
        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as exc:
            raise ValueError(f"invocation was not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            # ValueError, not TypeError: from the caller's side this is a
            # malformed *value* on stdin, and __main__ maps ValueError to the
            # "bad invocation" exit code.
            raise ValueError("invocation must be a JSON object")  # noqa: TRY004
        return cls(
            mission_id=str(data.get("mission_id") or ""),
            agent_id=str(data.get("agent_id") or "lead_scraper"),
            action=str(data.get("action") or "health"),
            payload=dict(data.get("payload") or {}),
            mission_workspace=str(data.get("mission_workspace") or ""),
        )


@dataclass
class Outcome:
    """What this agent reports back."""

    ok: bool
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    #: Set when the agent could not act because something is not configured.
    #: Distinct from an error: nothing malfunctioned, a prerequisite is absent.
    unavailable: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "summary": self.summary,
            "data": self.data,
            "error": self.error,
            "unavailable": self.unavailable,
        }

    def emit(self) -> None:
        """Print the result as the final stdout line, and exit-code accordingly."""
        sys.stdout.write("\n" + json.dumps(self.to_dict(), ensure_ascii=False) + "\n")
        sys.stdout.flush()


__all__ = ["Invocation", "Outcome"]
