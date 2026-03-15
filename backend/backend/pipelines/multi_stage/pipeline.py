"""MultiStagePipeline — wires all 5 stages with self-correction for code generation."""

from __future__ import annotations

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, GameResult, ProgressEvent
from backend.stages.code_generator import (
    _check_gdscript_syntax_patterns,
    run_code_generator,
)
from backend.stages.exporter import run_exporter
from backend.stages.game_designer import run_game_designer
from backend.stages.models import GameDesign
from backend.stages.prompt_enhancer import run_prompt_enhancer
from backend.stages.visual_polisher import run_visual_polisher

MAX_RETRIES = 2


async def _generate_code_with_correction(
    client: AsyncAnthropic,
    game_design: GameDesign,
    emit: EmitFn,
) -> dict[str, str]:
    """Run Code Generator with automatic self-correction on syntax errors.

    Retries up to MAX_RETRIES times if Python contamination patterns are
    detected in the generated GDScript.
    """
    files = await run_code_generator(client, game_design, emit, previous_error=None)
    syntax_error = _check_gdscript_syntax_patterns(files)

    if syntax_error is None:
        return files

    for _ in range(MAX_RETRIES):
        files = await run_code_generator(
            client, game_design, emit, previous_error=syntax_error
        )
        syntax_error = _check_gdscript_syntax_patterns(files)
        if syntax_error is None:
            return files

    raise RuntimeError(
        f"Code generation failed after {MAX_RETRIES} retries: {syntax_error}"
    )


class MultiStagePipeline:
    """Five-stage game generation pipeline with self-correcting code generation.

    Stages:
      1. Prompt Enhancer — raw prompt -> GameSpec
      2. Game Designer — GameSpec -> GameDesign
      3. Code Generator — GameDesign -> GDScript files (with self-correction)
      4. Visual Polisher — GDScript files + VisualStyle -> polished files
      5. Exporter — polished files -> assembled Godot project -> WASM
    """

    def __init__(self) -> None:
        self._client = AsyncAnthropic()

    async def generate(
        self, prompt: str, job_id: str, emit: EmitFn
    ) -> GameResult:
        """Run all pipeline stages and return the final GameResult."""
        try:
            # Stage 1: Prompt Enhancer
            game_spec = await run_prompt_enhancer(self._client, prompt, emit)

            # Stage 2: Game Designer
            game_design = await run_game_designer(self._client, game_spec, emit)

            # Stage 3: Code Generator with self-correction
            files = await _generate_code_with_correction(
                self._client, game_design, emit
            )

            # Stage 4: Visual Polisher
            polished_files = await run_visual_polisher(
                self._client, files, game_design.visual_style, emit
            )

            # Stage 5: Exporter
            result = await run_exporter(
                job_id,
                polished_files,
                [c.model_dump() for c in game_design.controls],
                emit,
            )

            await emit(ProgressEvent(type="done", message="Your game is ready."))
            await emit(None)  # type: ignore[arg-type]
            return result

        except Exception as e:
            await emit(ProgressEvent(type="error", message=str(e)))
            await emit(None)  # type: ignore[arg-type]
            raise
