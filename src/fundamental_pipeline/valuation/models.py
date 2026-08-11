"""Small closed, immutable value types for exact artifact references and
context projections.

These are thin, validated wrappers over the plain-dict shapes that
:mod:`~fundamental_pipeline.valuation.canonical`,
:mod:`~fundamental_pipeline.valuation.identity`, and
:mod:`~fundamental_pipeline.valuation.references` already operate on --
callers may use either the dataclass or the equivalent dict; the
functions in those modules never require the dataclass form.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ArtifactReferenceError


@dataclass(frozen=True)
class ArtifactReference:
    """An exact reference to a valuation artifact: type, ID, and relative
    path -- all three required, matching
    :data:`fundamental_pipeline.valuation.references.REQUIRED_REFERENCE_FIELDS`."""

    artifact_id: str
    artifact_type: str
    relative_path: str

    def __post_init__(self) -> None:
        for field_name in ("artifact_id", "artifact_type", "relative_path"):
            if not getattr(self, field_name):
                raise ArtifactReferenceError(f"ArtifactReference.{field_name} must be non-empty")

    def to_dict(self) -> dict[str, str]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "relative_path": self.relative_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ArtifactReference":
        return cls(
            artifact_id=data["artifact_id"],
            artifact_type=data["artifact_type"],
            relative_path=data["relative_path"],
        )

