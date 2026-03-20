"""Agentic pipeline data models.

Defines the structured types used throughout the agentic pipeline:
- AgenticGameSpec: rich game specification from the first LLM turn
- VerifierTask: individual task (edit/create) identified by the verifier
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


class VerifierTask(BaseModel):
    """A single task identified by the verifier agent.

    Each task is either an edit to an existing file or a request to create
    a new file that's missing from the project.
    """

    action: Literal["edit", "create"]
    file: str
    description: str
    severity: Literal["critical", "warning"]


class VerifierResult(BaseModel):
    """Aggregated verifier output — task list plus a human-readable summary."""

    tasks: list[VerifierTask]
    summary: str

    @property
    def has_critical_tasks(self) -> bool:
        """Return True if any task has severity 'critical'."""
        return any(t.severity == "critical" for t in self.tasks)
