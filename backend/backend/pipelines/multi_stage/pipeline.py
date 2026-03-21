"""MultiStagePipeline — wires all 5 stages with self-correction for code generation."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, GameResult, ProgressEvent
from backend.pipelines.exporter import GAMES_DIR, run_exporter
from backend.pipelines.multi_stage.code_generator import run_code_generator
from backend.pipelines.multi_stage.game_designer import run_game_designer
from backend.pipelines.multi_stage.prompt_enhancer import run_prompt_enhancer
from backend.pipelines.multi_stage.visual_polisher import run_visual_polisher


def _slugify(title: str, max_len: int = 40) -> str:
    """Convert a game title to a filesystem-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len].rstrip("-")


class MultiStagePipeline:
    """Five-stage game generation pipeline with self-correcting code generation.

    Stages:
      1. Prompt Enhancer — raw prompt -> GameSpec
      2. Game Designer — GameSpec -> GameDesign
      3. Code Generator — GameDesign -> GDScript files (with self-correction)
      4. Visual Polisher — GDScript files + VisualStyle -> polished files
      5. Exporter — polished files -> assembled Godot project -> WASM
    """

    def __init__(self, *, skip_polish: bool = True) -> None:
        self._client = AsyncAnthropic(max_retries=5)
        self._skip_polish = skip_polish

    async def generate(
        self,
        prompt: str,
        emit: EmitFn,
        *,
        save_intermediate: bool = True,
        **kwargs,
    ) -> GameResult:
        """Run all pipeline stages and return the final GameResult."""
        try:
            # Stage 1: Prompt Enhancer
            game_spec = await run_prompt_enhancer(self._client, prompt, emit)

            # Build a human-readable directory name: slugified-title_YYYYMMDD-HHMMSS
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            game_dir = f"{_slugify(game_spec.title)}_{timestamp}"

            # Set up intermediate output directory
            dump_dir = (
                GAMES_DIR / game_dir / "intermediate" if save_intermediate else None
            )
            if dump_dir:
                dump_dir.mkdir(parents=True, exist_ok=True)
                (dump_dir / "1_game_spec.json").write_text(
                    game_spec.model_dump_json(indent=2)
                )

            # Stage 2: Game Designer
            game_design = await run_game_designer(self._client, game_spec, emit)
            if dump_dir:
                (dump_dir / "2_game_design.json").write_text(
                    game_design.model_dump_json(indent=2)
                )

            # Stage 3: Code Generator (validates + repairs internally)
            files = await run_code_generator(self._client, game_design, emit)
            if dump_dir:
                code_dir = dump_dir / "3_code_generator"
                code_dir.mkdir(exist_ok=True)
                for name, content in files.items():
                    (code_dir / name).write_text(content)

            # Stage 4: Visual Polisher (optional)
            if self._skip_polish:
                export_files = files
            else:
                export_files = await run_visual_polisher(
                    self._client, files, game_design.visual_style, emit
                )
                if dump_dir:
                    polish_dir = dump_dir / "4_visual_polisher"
                    polish_dir.mkdir(exist_ok=True)
                    for name, content in export_files.items():
                        (polish_dir / name).write_text(content)

            # Stage 5: Exporter
            result = await run_exporter(
                game_dir,
                export_files,
                [c.model_dump() for c in game_design.controls],
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
            await emit(None)  # type: ignore[arg-type]
            return result

        except Exception as e:
            await emit(ProgressEvent(type="error", message=str(e)))
            await emit(None)  # type: ignore[arg-type]
            raise
