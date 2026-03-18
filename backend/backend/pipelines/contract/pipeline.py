"""Contract-first parallel pipeline for game generation.

This pipeline uses typed data contracts (RichGameSpec, GameContract) to
define inter-stage interfaces, enabling topological wave scheduling
for parallel node generation.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, GameResult, ProgressEvent
from backend.stages.contract_generator import run_contract_generator
from backend.stages.exporter import GAMES_DIR, run_exporter
from backend.stages.game_manager_generator import generate_game_manager_script_async
from backend.stages.node_generator import run_parallel_node_generation
from backend.stages.spec_expander import run_spec_expander
from backend.stages.wiring_generator import run_wiring_generator


def _strip_node_tscn(node_files: dict[str, str]) -> dict[str, str]:
    """Remove .tscn files from node generator output.

    Per-node .tscn files from the LLM frequently contain mismatched
    ExtResource IDs and incorrect script attachments (Bugs C, F).
    The wiring stage owns all scene assembly from the contract.
    """
    return {k: v for k, v in node_files.items() if not k.endswith(".tscn")}


def _slugify(title: str, max_len: int = 40) -> str:
    """Convert a game title to a filesystem-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len].rstrip("-")


class ContractPipeline:
    """Contract-first pipeline that satisfies the GamePipeline Protocol.

    Stages:
      1. Spec Expander     -- raw prompt -> RichGameSpec
      2. Contract Generator -- RichGameSpec -> GameContract
      3. Node Generator     -- GameContract -> per-node scripts (parallel waves)
      4. Wiring Generator   -- GameContract + scripts -> Main.tscn + project.godot
      5. Exporter           -- assembled project dir -> WASM
    """

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
        try:
            await emit(
                ProgressEvent(
                    type="stage_start",
                    message="Starting contract pipeline...",
                )
            )

            # Stage 1: Spec Expander — prompt -> RichGameSpec
            spec = await run_spec_expander(self._client, prompt, emit)

            # Build a human-readable directory name
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            game_dir = f"{_slugify(spec.title)}_{timestamp}"

            # Set up intermediate output directory
            dump_dir = (
                GAMES_DIR / game_dir / "intermediate"
                if save_intermediate
                else None
            )
            if dump_dir:
                dump_dir.mkdir(parents=True, exist_ok=True)
                (dump_dir / "1_rich_game_spec.json").write_text(
                    spec.model_dump_json(indent=2)
                )

            # Stage 2: Contract Generator — RichGameSpec -> GameContract
            contract = await run_contract_generator(self._client, spec, emit)
            if dump_dir:
                (dump_dir / "2_game_contract.json").write_text(
                    contract.model_dump_json(indent=2)
                )

            # Stage 2.5: Generate game-specific game_manager.gd from contract
            await emit(
                ProgressEvent(
                    type="stage_start",
                    message="Generating GameManager with method implementations...",
                )
            )
            game_manager_code = await generate_game_manager_script_async(
                self._client, contract
            )
            gm_files = {"game_manager.gd": game_manager_code}
            if dump_dir:
                (dump_dir / "2.5_game_manager.gd").write_text(game_manager_code)

            # Stage 3: Parallel Node Generation — GameContract -> per-node scripts
            node_files = await run_parallel_node_generation(
                self._client, contract, emit
            )

            # Strip per-node .tscn files — wiring stage owns all scene assembly.
            # Per-node .tscn from the LLM frequently has invalid ExtResource IDs
            # and wrong script attachments (Bugs C, F).
            node_files = _strip_node_tscn(node_files)

            if dump_dir:
                node_dir = dump_dir / "3_node_files"
                node_dir.mkdir(exist_ok=True)
                for name, content in node_files.items():
                    (node_dir / name).write_text(content)

            # Stage 4: Wiring Generator — contract + scripts -> Main.tscn + project.godot
            wiring_files = await run_wiring_generator(
                self._client, contract, node_files, emit
            )
            if dump_dir:
                wiring_dir = dump_dir / "4_wiring_files"
                wiring_dir.mkdir(exist_ok=True)
                for name, content in wiring_files.items():
                    (wiring_dir / name).write_text(content)

            # Merge all generated files (gm_files first so node/wiring can override if needed)
            all_files = {**gm_files, **node_files, **wiring_files}

            # Stage 5: Exporter — assembled project -> WASM
            result = await run_exporter(
                game_dir,
                all_files,
                contract.controls,
                emit,
            )
            if dump_dir:
                (dump_dir / "5_result.json").write_text(
                    result.model_dump_json(indent=2)
                )

            await emit(
                ProgressEvent(
                    type="done",
                    message="Your game is ready.",
                    data={
                        "job_id": result.job_id,
                        "wasm_path": result.wasm_path,
                        "controls": result.controls,
                    },
                )
            )
            await emit(None)  # type: ignore[arg-type]  # sentinel to signal SSE stream end
            return result

        except Exception as e:
            await emit(ProgressEvent(type="error", message=str(e)))
            await emit(None)  # type: ignore[arg-type]
            raise
