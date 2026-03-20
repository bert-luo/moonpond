"""Agentic pipeline data models.

Defines the structured types used throughout the agentic pipeline:
- AgenticGameSpec: rich game specification from the first LLM turn
- VerifierError: individual error found by the verifier
- VerifierResult: aggregated verifier output with severity checking
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ControlMapping(BaseModel):
    """A single input → action mapping for the generated game."""

    key: str
    action: str


class AgenticGameSpec(BaseModel):
    """Rich game specification produced by the spec generator.

    Agentic-native model — deliberately not reusing RichGameSpec from the
    contract pipeline, per user decision in CONTEXT.md.
    """

    title: str
    genre: str
    mechanics: list[str]
    entities: list[dict]
    scene_description: str
    win_condition: str
    fail_condition: str
    controls: list[ControlMapping] = []
    perspective: Literal["2D", "3D"] = "2D"


class VerifierError(BaseModel):
    """A single error found by the verifier agent."""

    file_path: str
    error_type: Literal["syntax", "reference", "logic", "missing"]
    description: str
    severity: Literal["critical", "warning"]


class VerifierResult(BaseModel):
    """Aggregated verifier output — list of errors plus a human-readable summary."""

    errors: list[VerifierError]
    summary: str

    @property
    def has_critical_errors(self) -> bool:
        """Return True if any error has severity 'critical'."""
        return any(e.severity == "critical" for e in self.errors)
