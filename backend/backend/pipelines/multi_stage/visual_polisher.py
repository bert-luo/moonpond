"""Visual Polisher stage — adds shader, palette, and particle polish to GDScript files."""

from __future__ import annotations

import json
import re

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, ProgressEvent
from backend.pipelines.assets import PALETTE_PATHS, PARTICLE_PATHS, SHADER_PATHS
from backend.pipelines.multi_stage.models import VisualStyle

SONNET_MODEL = "claude-sonnet-4-6"

# Build the asset path listing dynamically from the model constants
_shader_list = "\n".join(f"  - {k}: {v}" for k, v in SHADER_PATHS.items())
_palette_list = "\n".join(f"  - {k}: {v}" for k, v in PALETTE_PATHS.items())
_particle_list = "\n".join(f"  - {k}: {v}" for k, v in PARTICLE_PATHS.items())

_POLISHER_SYSTEM_PROMPT = f"""\
You are a visual effects artist for Godot 4 games. Your job is to review GDScript \
files and add visual polish using the template asset library.

REQUIREMENTS:
- You MUST add at least one shader reference
- You MUST add at least one palette selection
- You MAY add particle scene references where appropriate
- Do NOT modify control logic or game mechanics — only add visual enhancements
- Never write to res://assets/ — only modify script files

Available assets:

Shaders:
{_shader_list}

Palettes:
{_palette_list}

Particles:
{_particle_list}

How to apply a shader:
  var shader = preload("res://assets/shaders/pixel_art.gdshader")
  var mat = ShaderMaterial.new()
  mat.shader = shader
  sprite.material = mat

How to apply a palette (gradient resource):
  var palette = preload("res://assets/palettes/neon.tres")

How to instance a particle scene:
  var particles = preload("res://assets/particles/dust.tscn").instantiate()
  add_child(particles)

Respond ONLY with a JSON object where keys are filenames and values are the \
COMPLETE patched GDScript source code (not diffs). Include ALL files from the \
input, even if unchanged. Do NOT include markdown code fences — respond with \
raw JSON only.\
"""


async def run_visual_polisher(
    client: AsyncAnthropic,
    files: dict[str, str],
    visual_style: VisualStyle,
    emit: EmitFn,
) -> dict[str, str]:
    """Patch GDScript files to add visual polish via LLM.

    Args:
        client: Anthropic async client.
        files: Dict mapping filename to GDScript source code.
        visual_style: The desired visual style (palette, shader, mood).
        emit: Async callback for progress events.

    Returns:
        Dict mapping filename to patched GDScript source code.
    """
    await emit(
        ProgressEvent(type="stage_start", message="Adding visual polish...")
    )

    user_message = (
        f"Visual style to apply:\n"
        f"  palette: {visual_style.palette}\n"
        f"  shader: {visual_style.shader}\n"
        f"  mood: {visual_style.mood}\n\n"
        f"Current GDScript files:\n{json.dumps(files, indent=2)}"
    )

    response = await client.messages.create(
        model=SONNET_MODEL,
        max_tokens=16384,
        system=_POLISHER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        stream=True,
    )

    collected_text = []
    async for event in response:
        if event.type == "content_block_delta" and hasattr(event.delta, "text"):
            collected_text.append(event.delta.text)
    raw = "".join(collected_text).strip()

    # Extract JSON from markdown fences or preamble text.
    # The LLM sometimes adds explanatory text before the JSON block.
    fence_match = re.search(r"```(?:json)?\s*\n(\{.*)\n\s*```", raw, re.DOTALL)
    if fence_match:
        raw = fence_match.group(1).strip()
    elif raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    elif not raw.startswith("{"):
        json_start = raw.find("{")
        if json_start > 0:
            raw = raw[json_start:]

    patched_files: dict[str, str] = json.loads(raw)
    return patched_files
