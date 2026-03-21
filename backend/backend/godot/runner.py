"""Async Godot headless export runner.

Executes Godot's --export-release in a subprocess without blocking the
asyncio event loop.  Validates success by checking that the output file
exists on disk rather than relying on the process exit code (Godot
issue #83042 — non-zero exit even on successful export).
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from subprocess import DEVNULL, PIPE


# Resolve GODOT_BIN: env var override, else platform-appropriate default
_REPO_ROOT = Path(__file__).parent.parent.parent.parent  # backend/backend/godot -> repo root
_MACOS_GODOT = _REPO_ROOT / "godot" / "Godot.app" / "Contents" / "MacOS" / "Godot"
_LINUX_GODOT = Path("/usr/local/bin/godot")


def _default_godot_bin() -> str:
    """Return the best default Godot binary path for the current platform."""
    if _MACOS_GODOT.exists():
        return str(_MACOS_GODOT)
    if _LINUX_GODOT.exists():
        return str(_LINUX_GODOT)
    # Fallback to macOS path (original behaviour)
    return str(_MACOS_GODOT)


GODOT_BIN: str = os.environ.get("GODOT_BIN", _default_godot_bin())
"""Path to the Godot editor binary."""


@dataclass
class RunResult:
    """Result of a headless Godot export."""

    success: bool
    stderr: str
    output_path: Path | None


async def run_headless_export(
    project_path: Path,
    output_dir: Path,
    preset_name: str = "Web",
) -> RunResult:
    """Run Godot headless export and return the result.

    Args:
        project_path: Path to the Godot project directory (contains project.godot).
        output_dir: Directory where the exported files will be written.
        preset_name: Name of the export preset (default "Web").

    Returns:
        RunResult with success status, captured stderr, and output path.
    """
    output_path = output_dir / "index.html"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        proc = await asyncio.create_subprocess_exec(
            GODOT_BIN,
            "--headless",
            "--path",
            str(project_path),
            "--export-release",
            preset_name,
            str(output_path),
            stdout=DEVNULL,
            stderr=PIPE,
        )
    except (FileNotFoundError, OSError) as e:
        return RunResult(
            success=False,
            stderr=f"Failed to launch Godot binary ({GODOT_BIN}): {e}",
            output_path=None,
        )

    _, raw_stderr = await proc.communicate()
    stderr_text = raw_stderr.decode(errors="replace") if raw_stderr else ""

    # Validate by file existence, NOT exit code (Godot issue #83042)
    success = output_path.exists()

    return RunResult(
        success=success,
        stderr=stderr_text,
        output_path=output_path if success else None,
    )
