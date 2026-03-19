"""Wiring Generator stage — produces Main.tscn and optionally project.godot.

This stage assembles the scene tree from the contract and generated files,
ensuring correct ExtResource references and signal connections.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, ProgressEvent
from backend.pipelines.contract.models import GameContract

logger = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-6"

# Autoload names that are always hardcoded in the [autoload] section.
# Contract autoloads with these names are skipped to prevent duplicates.
_HARDCODED_AUTOLOAD_NAMES: frozenset[str] = frozenset({"GameManager"})

_REPO_ROOT = Path(
    __file__
).parent.parent.parent.parent.parent  # contract -> pipelines -> backend -> backend -> repo root
TEMPLATE_DIR = _REPO_ROOT / "godot" / "templates" / "base_2d"


def _build_wiring_system_prompt(
    contract: GameContract,
    generated_files: dict[str, str],
) -> str:
    """Build the system prompt for Main.tscn generation.

    Filters out dynamic nodes (spawn_mode='dynamic') from the contract
    and generated files since they are instantiated at runtime, not
    placed in the scene tree.
    """
    # Filter to static nodes only for scene tree assembly
    static_nodes = [n for n in contract.nodes if n.spawn_mode == "static"]
    static_contract = contract.model_copy(update={"nodes": static_nodes})

    # Filter generated files to exclude dynamic node scripts
    dynamic_script_paths = {n.script_path for n in contract.nodes if n.spawn_mode == "dynamic"}
    static_generated_files = {k: v for k, v in generated_files.items() if k not in dynamic_script_paths}

    parts = [
        "Generate a Godot 4 text-format Main.tscn file that wires all these nodes together.",
        "",
        f"Full game contract:\n{static_contract.model_dump_json(indent=2)}",
        "",
        f"Actually generated files: {json.dumps(sorted(static_generated_files.keys()))}",
        "",
        "Rules:",
        "- Dynamic nodes (spawn_mode='dynamic') are excluded from the scene tree — "
        "they are instantiated at runtime by other scripts.",
        "- Use [ext_resource] with unique incrementing integer IDs for each script.",
        "- Each node in the scene tree must reference the correct script via its ext_resource ID.",
        "- The root node should be a Node2D named 'Main'.",
        "- Connect signals as specified in the node contracts.",
        "- All ext_resource paths use res:// (project root).",
        "- Node names must be unique among siblings.",
        "- Set unique_name_in_owner = true on EVERY node that has a script attached. "
        "This allows scripts to reference siblings via %NodeName instead of brittle paths.",
        "",
        "Respond with ONLY the Main.tscn file content. No markdown fences, no explanation.",
    ]
    return "\n".join(parts)


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
        # Convention: autoload script is snake_case version of the name
        script = name[0].lower() + name[1:]
        # Convert CamelCase to snake_case for the script filename
        script_snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        autoload_lines.append(f'{name}="*res://{script_snake}.gd"\n')

    new_autoload = "".join(autoload_lines)

    # Replace existing [autoload] section (up to the next section header)
    pattern = r"\[autoload\]\s*\n(?:.*\n)*?(?=\[|\Z)"
    result = re.sub(pattern, new_autoload + "\n", template_content)
    return result


async def run_wiring_generator(
    client: AsyncAnthropic,
    contract: GameContract,
    generated_files: dict[str, str],
    emit: EmitFn,
) -> dict[str, str]:
    """Generate Main.tscn and optionally project.godot from the contract.

    Returns dict mapping filename -> content for wiring files only.
    """
    await emit(ProgressEvent(type="stage_start", message="Wiring scene tree..."))

    # Generate Main.tscn via LLM
    system_prompt = _build_wiring_system_prompt(contract, generated_files)
    user_message = (
        "Generate the Main.tscn file for this game. "
        "Wire all nodes with correct ExtResource references."
    )

    response = await client.messages.create(
        model=SONNET_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\s*\n?", "", raw)
        raw = re.sub(r"\n?\s*```\s*$", "", raw)

    wiring_files: dict[str, str] = {"Main.tscn": raw}

    # Optionally patch project.godot for autoloads
    if contract.autoloads:
        template_path = TEMPLATE_DIR / "project.godot"
        template_content = template_path.read_text()
        patched = _patch_project_godot_autoloads(template_content, contract.autoloads)
        wiring_files["project.godot"] = patched

    return wiring_files
