"""Exporter stage — assembles a Godot project from generated scripts and exports WASM."""

from __future__ import annotations

import shutil
from pathlib import Path

from backend.godot.runner import run_headless_export
from backend.pipelines.base import EmitFn, GameResult, ProgressEvent

_REPO_ROOT = Path(__file__).parent.parent.parent.parent  # stages -> backend -> backend -> repo root
TEMPLATE_DIR = _REPO_ROOT / "godot" / "templates" / "base_2d"
GAMES_DIR = _REPO_ROOT / "games"


async def run_exporter(
    job_id: str,
    files: dict[str, str],
    controls: list[dict],
    emit: EmitFn,
) -> GameResult:
    """Assemble a Godot project from generated scripts and export to WASM.

    Args:
        job_id: Unique identifier for this generation job.
        files: Dict mapping filename to GDScript source code.
        controls: List of control mapping dicts for the frontend.
        emit: Async callback for progress events.

    Returns:
        GameResult with the WASM path and control mappings.

    Raises:
        RuntimeError: If the Godot headless export fails.
    """
    await emit(
        ProgressEvent(type="stage_start", message="Building for web...")
    )

    project_dir = GAMES_DIR / job_id / "project"
    export_dir = GAMES_DIR / job_id / "export"

    # Copy the base template (dirs_exist_ok=True per Pitfall 6)
    shutil.copytree(TEMPLATE_DIR, project_dir, dirs_exist_ok=True)

    # Write generated scripts into the scripts/ subdirectory
    scripts_dir = project_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)

    for filename, content in files.items():
        (scripts_dir / filename).write_text(content)

    # Run Godot headless export
    result = await run_headless_export(project_dir, export_dir)

    if not result.success:
        raise RuntimeError(f"Export failed: {result.stderr[:500]}")

    return GameResult(
        job_id=job_id,
        wasm_path=f"/games/{job_id}/export/index.html",
        controls=controls,
    )
