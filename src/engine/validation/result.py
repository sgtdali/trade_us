"""Structured validation results shared across every validation layer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationFinding:
    code: str
    severity: str  # "error" | "warning" | "info"
    message: str
    file: str | None = None
    path: str | None = None
    remediation: str | None = None

    def __str__(self) -> str:
        location = f" [{self.file}{('#' + self.path) if self.path else ''}]" if self.file else ""
        return f"{self.code}: {self.message}{location}"


@dataclass
class ValidationResult:
    errors: list[ValidationFinding] = field(default_factory=list)
    warnings: list[ValidationFinding] = field(default_factory=list)
    info: list[ValidationFinding] = field(default_factory=list)

    def add(self, finding: ValidationFinding) -> None:
        {"error": self.errors, "warning": self.warnings, "info": self.info}[finding.severity].append(finding)

    def merge(self, other: "ValidationResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.extend(other.info)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": [str(f) for f in self.errors],
            "warnings": [str(f) for f in self.warnings],
            "info": [str(f) for f in self.info],
        }
