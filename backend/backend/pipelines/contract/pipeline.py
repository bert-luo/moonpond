"""Contract-first parallel pipeline for game generation.

This pipeline uses typed data contracts (RichGameSpec, GameContract) to
define inter-stage interfaces, enabling topological wave scheduling
for parallel node generation.
"""

from __future__ import annotations

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, GameResult, ProgressEvent
from backend.stages.contract_models import GameContract, RichGameSpec  # noqa: F401 — proves import chain


class ContractPipeline:
    """Contract-first pipeline that satisfies the GamePipeline Protocol."""

    def __init__(self) -> None:
        self._client = AsyncAnthropic()

    async def generate(
        self,
        prompt: str,
        job_id: str,
        emit: EmitFn,
        *,
        save_intermediate: bool = True,
    ) -> GameResult:
        """Generate a game from a text prompt using contract-first stages.

        Parameters match the GamePipeline Protocol signature exactly.
        """
        await emit(ProgressEvent(type="stage_start", message="Starting contract pipeline..."))

        # TODO: Stage 1 — spec_expander: prompt -> RichGameSpec
        # TODO: Stage 2 — contract_generator: RichGameSpec -> GameContract
        # TODO: Stage 3 — node_generator: GameContract -> per-node scripts (parallel waves)
        # TODO: Stage 4 — wiring_generator: GameContract + scripts -> Main.tscn + GameManager
        # TODO: Stage 5 — exporter: project dir -> WASM

        await emit(ProgressEvent(type="done", message="Your game is ready.", data={"job_id": job_id}))
        await emit(None)  # type: ignore[arg-type]  # sentinel to signal SSE stream end

        return GameResult(job_id=job_id, wasm_path="", controls=[])
