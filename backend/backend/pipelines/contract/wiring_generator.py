"""Wiring utilities -- project.godot autoload patching.

The LLM-based wiring generator has been removed. Scene assembly is now
handled deterministically by SceneAssembler. This module retains only
the project.godot autoload patching logic used by the pipeline.
"""

from __future__ import annotations

import re
from pathlib import Path

# Autoload names that are always hardcoded in the [autoload] section.
# Contract autoloads with these names are skipped to prevent duplicates.
_HARDCODED_AUTOLOAD_NAMES: frozenset[str] = frozenset({"GameManager"})

_REPO_ROOT = Path(
    __file__
).parent.parent.parent.parent.parent  # contract -> pipelines -> backend -> backend -> repo root
TEMPLATE_DIR = _REPO_ROOT / "godot" / "templates" / "base_2d"


def _patch_project_godot_autoloads(
    template_content: str,
    autoloads: list[str],
) -> str:
    """Replace the [autoload] section in project.godot, preserving everything else.

    CRITICAL: The [input] section must remain untouched.
    """
    # Build new autoload section
    autoload_lines = ["[autoload]\n", "\n", 'GameManager="*res://game_manager.gd"\n']
    for name in autoloads:
        if name in _HARDCODED_AUTOLOAD_NAMES:
            continue  # already emitted in hardcoded list above
        # Convert CamelCase to snake_case for the script filename
        script_snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        autoload_lines.append(f'{name}="*res://{script_snake}.gd"\n')

    new_autoload = "".join(autoload_lines)

    # Replace existing [autoload] section (up to the next section header)
    pattern = r"\[autoload\]\s*\n(?:.*\n)*?(?=\[|\Z)"
    result = re.sub(pattern, new_autoload + "\n", template_content)
    return result
