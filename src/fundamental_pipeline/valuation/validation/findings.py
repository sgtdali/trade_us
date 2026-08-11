"""The deterministic base-validation finding contract (T68.1 subset active
in T70-A: identity, parse-safety, schema, and catalog/lock findings).

A finding never carries localized human prose as its identity: identity is
``rule_id`` + canonical location + ``reason_code`` + canonical parameters.
Rendered ``message`` text is presentation only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from ..canonical import canonical_bytes

SEVERITY_RANK = {"blocker": 0, "error": 1, "warning": 2, "info": 3}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str  # "info" | "warning" | "error" | "blocker"
    scope: str  # "field" | "artifact" | "catalog" | "bundle" | "schema"
    message: str
    reason_code: str | None = None
    artifact_type: str | None = None
    artifact_id: str | None = None
    relative_path: str | None = None
    json_pointer: str = ""
    related_reference_ids: tuple[str, ...] = field(default_factory=tuple)
    message_params: dict[str, Any] = field(default_factory=dict)
    recoverability: str | None = None

    @property
    def finding_id(self) -> str:
        """Deterministic finding identity: sha256 over rule_id, artifact
        location, json_pointer, sorted related reference IDs, reason_code,
        and canonical message_params. Two structurally identical findings
        always produce the same finding_id; two distinct findings (almost)
        never collide."""
        preimage = {
            "rule_id": self.rule_id,
            "artifact_type": self.artifact_type,
            "artifact_id": self.artifact_id,
            "relative_path": self.relative_path,
            "json_pointer": self.json_pointer,
            "related_reference_ids": sorted(self.related_reference_ids),
            "reason_code": self.reason_code,
            "message_params": self.message_params,
        }
        digest = hashlib.sha256(canonical_bytes(preimage)).hexdigest()
        return f"finding-{digest[:32]}"

    def sort_key(self) -> tuple:
        return (
            self.relative_path or "",
            self.json_pointer or "",
            self.rule_id,
            tuple(sorted(self.related_reference_ids)),
        )


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Sort findings deterministically: relative_path, then JSON pointer,
    then rule_id, then related reference IDs. Iteration order of any
    parallel collection or mapping never affects this output."""
    return sorted(findings, key=Finding.sort_key)


def has_blocking(findings: list[Finding], *, warnings_as_errors: bool = False) -> bool:
    for finding in findings:
        if finding.severity in ("error", "blocker"):
            return True
        if warnings_as_errors and finding.severity == "warning":
            return True
    return False
