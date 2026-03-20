"""Exporter stage — assembles a Godot project from generated scripts and exports WASM."""

from __future__ import annotations

import shutil
from pathlib import Path

from backend.godot.runner import run_headless_export
from backend.pipelines.base import EmitFn, GameResult, ProgressEvent

_REPO_ROOT = Path(__file__).parent.parent.parent.parent  # pipelines -> backend -> backend -> repo root
TEMPLATE_DIR_2D = _REPO_ROOT / "godot" / "templates" / "base_2d"
TEMPLATE_DIR_3D = _REPO_ROOT / "godot" / "templates" / "base_3d"
GAMES_DIR = _REPO_ROOT / "games"


def get_template_dir(perspective: str) -> Path:
    """Return the template directory for the given perspective.

    Args:
        perspective: "2D" or "3D".

    Returns:
        Path to the appropriate base template directory.
    """
    if perspective == "3D":
        return TEMPLATE_DIR_3D
    return TEMPLATE_DIR_2D


async def run_exporter(
    game_dir: str,
    files: dict[str, str],
    controls: list[dict],
    emit: EmitFn,
    *,
    perspective: str = "2D",
) -> GameResult:
    """Assemble a Godot project from generated scripts and export to WASM.

    Args:
        game_dir: Human-readable directory name (e.g. "space-invaders_20260316-041200").
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

    project_dir = GAMES_DIR / game_dir / "project"
    export_dir = GAMES_DIR / game_dir / "export"

    # Copy the base template (dirs_exist_ok=True per Pitfall 6)
    shutil.copytree(get_template_dir(perspective), project_dir, dirs_exist_ok=True)

    # Write generated files into the project
    # .tscn and .gd files go to project root (matching res:// paths in generated code)
    for filename, content in files.items():
        (project_dir / filename).write_text(content)

    # Run Godot headless export
    result = await run_headless_export(project_dir, export_dir)

    if not result.success:
        raise RuntimeError(f"Export failed: {result.stderr[:500]}")

    return GameResult(
        job_id=game_dir,
        wasm_path=f"/games/{game_dir}/export/index.html",
        controls=controls,
    )
