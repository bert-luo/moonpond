"""Core pipeline types: GamePipeline Protocol, ProgressEvent, GameResult, EmitFn."""

from __future__ import annotations

import asyncio
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


class SoftTimeout:
    """Cooperative soft timeout using an asyncio.Event.

    The pipeline checks ``is_expired`` at natural breakpoints to decide
    whether to skip remaining work and proceed to export.
    """

    def __init__(self, seconds: float) -> None:
        self._event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._seconds = seconds

    async def _timer(self) -> None:
        await asyncio.sleep(self._seconds)
        self._event.set()

    def start(self) -> None:
        """Start the countdown. Must be called inside a running event loop."""
        self._task = asyncio.create_task(self._timer())

    @property
    def is_expired(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        if self._task:
            self._task.cancel()


class GamePipeline(Protocol):
    """Protocol that all pipeline strategies must satisfy."""

    async def generate(
        self, prompt: str, job_id: str, emit: EmitFn,
        *, save_intermediate: bool = True,
        soft_timeout: SoftTimeout | None = None,
    ) -> GameResult: ...
