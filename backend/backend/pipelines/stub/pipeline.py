"""Stub pipeline: copies base_2d template, writes a dummy GDScript, runs Godot export.

This is the minimal end-to-end proof that the pipeline chain works.
Replaced by MultiStagePipeline in Phase 3.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..base import EmitFn, GameResult, ProgressEvent
from ...godot.runner import run_headless_export

_REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent  # backend/backend/pipelines/stub -> repo root
TEMPLATE_DIR = _REPO_ROOT / "godot" / "templates" / "base_2d"
GAMES_DIR = _REPO_ROOT / "games"


class StubPipeline:
    """Minimal GamePipeline implementation for end-to-end testing."""

    async def generate(self, prompt: str, job_id: str, emit: EmitFn, *, save_intermediate: bool = True) -> GameResult:
        await emit(ProgressEvent(type="stage_start", message="Setting up project..."))

        project_dir = GAMES_DIR / job_id / "project"
        export_dir = GAMES_DIR / job_id / "export"

        # Copy template
        shutil.copytree(TEMPLATE_DIR, project_dir)

        # Write dummy GDScript to prove file injection works
        scripts_dir = project_dir / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        (scripts_dir / "generated_main.gd").write_text(
            f'extends Node\nfunc _ready(): print("stub pipeline job: {job_id}")'
        )

        await emit(ProgressEvent(type="stage_start", message="Building for web..."))

        result = await run_headless_export(project_dir, export_dir)
        if not result.success:
            await emit(
                ProgressEvent(
                    type="error",
                    message="Export failed",
                    data={"stderr": result.stderr},
                )
            )
            await emit(None)
            raise RuntimeError(f"Godot export failed: {result.stderr[:500]}")

        await emit(ProgressEvent(type="done", message="Your game is ready."))
        await emit(None)

        return GameResult(
            job_id=job_id, wasm_path=f"/games/{job_id}/export/index.html"
        )
