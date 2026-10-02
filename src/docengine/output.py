"""Stable machine-readable command result envelope for P6+ CLI/AI protocol."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .versions import ENGINE_VERSION, MACHINE_OUTPUT_SCHEMA_VERSION


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    severity: str = "error"
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommandResult:
    """One logical command result, rendered identically for human/JSON surfaces.

    ``status`` remains an internal/human label and is surfaced under ``meta`` in the
    frozen P6 JSON envelope.  Issues are split into warnings/errors without changing
    the underlying facts.
    """

    command: str
    ok: bool
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    issues: tuple[Issue, ...] = ()
    attention_required: bool = False
    machine_output_schema_version: str = MACHINE_OUTPUT_SCHEMA_VERSION
    engine_version: str = ENGINE_VERSION

    def to_dict(self, *, exit_code: int = 0) -> dict[str, Any]:
        warnings = [issue.to_dict() for issue in self.issues if issue.severity != "error"]
        errors = [issue.to_dict() for issue in self.issues if issue.severity == "error"]
        return {
            "schema_version": self.machine_output_schema_version,
            "command": self.command,
            "ok": self.ok,
            "attention_required": self.attention_required,
            "data": self.data,
            "warnings": warnings,
            "errors": errors,
            "meta": {
                "engine_version": self.engine_version,
                "status": self.status,
                "exit_code": exit_code,
            },
        }
