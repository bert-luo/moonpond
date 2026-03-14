"""Core pipeline types: GamePipeline Protocol, ProgressEvent, GameResult, EmitFn."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from pydantic import BaseModel


class ProgressEvent(BaseModel):
    """SSE progress event pushed to the client during game generation."""

    type: str  # stage_start | stage_complete | error | done
    message: str
    data: dict = {}


class GameResult(BaseModel):
    """Final result of a pipeline run."""

    job_id: str
    wasm_path: str
    controls: list[dict] = []


EmitFn = Callable[[ProgressEvent], Awaitable[None]]
"""Async callback that pushes a ProgressEvent to the SSE stream."""


class GamePipeline(Protocol):
    """Protocol that all pipeline strategies must satisfy."""

    async def generate(
        self, prompt: str, job_id: str, emit: EmitFn
    ) -> GameResult: ...
