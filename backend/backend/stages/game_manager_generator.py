"""Game Manager GDScript generator -- produces a game-specific game_manager.gd from a GameContract.

Takes the static template base (palette, state management) and extends it with
contract-specified enums, properties, signals, and LLM-generated method implementations
so that node generators can reference a concrete GameManager API.
"""

from __future__ import annotations

import json
import logging
import re

from anthropic import AsyncAnthropic

from backend.stages.contract_models import GameContract

logger = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-20250514"

# Method names already defined in _TEMPLATE_BASE -- contract methods with these
# bare names must be filtered out to prevent duplicate func definitions.
_TEMPLATE_BASE_METHOD_NAMES: frozenset[str] = frozenset({
    "_ready", "set_palette", "get_palette_color", "set_state",
})


def _extract_method_name(signature: str) -> str:
    """Extract the bare method name from a GDScript signature.

    >>> _extract_method_name("set_state(new_state: int) -> void")
    'set_state'
    """
    return signature.split("(")[0].strip()

# ---------------------------------------------------------------------------
# Template base -- hardcoded from godot/templates/base_2d/game_manager.gd
# This is the static core that every generated game_manager.gd preserves.
# ---------------------------------------------------------------------------

_TEMPLATE_BASE = '''\
# game_manager.gd
# Autoloaded as GameManager -- available globally to all generated scenes.

extends Node

## Active color palette. Default: neon. Pipeline sets this before gameplay starts.
var active_palette: Gradient = null

## Game state tracking. Enum variants come from the game contract.
var state: int = 0

func _ready() -> void:
\t# Default palette: neon. Pipeline Visual Polisher overrides this.
\tactive_palette = load("res://assets/palettes/neon.tres")

## Set the active palette by name (matches filenames in assets/palettes/).
func set_palette(palette_name: String) -> void:
\tvar path := "res://assets/palettes/%s.tres" % palette_name
\tif ResourceLoader.exists(path):
\t\tactive_palette = load(path)
\telse:
\t\tpush_warning("GameManager: palette not found: " + path)

## Sample the active palette at position t (0.0 to 1.0).
func get_palette_color(t: float) -> Color:
\tif active_palette:
\t\treturn active_palette.sample(clampf(t, 0.0, 1.0))
\treturn Color.WHITE

## Called by generated scenes to update game state.
func set_state(new_state: int) -> void:
\tstate = new_state
'''


def _build_method_gen_prompt(contract: GameContract) -> str:
    """Build the system prompt for generating GameManager method bodies."""
    return """\
You are implementing GDScript method bodies for a Godot 4 GameManager autoload singleton.

Game: {title}

The GameManager has these properties (all declared as class-level vars):
{properties}

Enums available:
{enums}

Signals available (emit these where appropriate):
{signals}

Generate the method BODY (not the signature) for each of these methods:
{methods}

Rules:
- Use ONLY the properties, enums, and signals listed above. Do not invent new ones.
- Initialize properties to sensible defaults on first use if they are null \
(e.g. if points == null: points = 0).
- Emit relevant signals after state changes (e.g. emit points_changed after modifying points).
- Return correct types matching the signatures.
- Use tab indentation (real \\t characters, not spaces).
- Keep implementations simple and correct. No over-engineering.
- Each body should be 1-15 lines. These are state management methods, not complex logic.

Respond with ONLY a JSON object mapping each method signature (exactly as given) \
to its GDScript method body as a string. The body should NOT include the func line — \
only the indented lines that go inside it.
Do NOT include markdown code fences. Respond with raw JSON only.""".format(
        title=contract.title,
        properties="\n".join(f"  var {p}" for p in contract.game_manager_properties)
        if contract.game_manager_properties
        else "  (none)",
        enums="\n".join(
            f"  enum {name} {{ {', '.join(variants)} }}"
            for name, variants in contract.game_manager_enums.items()
        )
        if contract.game_manager_enums
        else "  (none)",
        signals="\n".join(f"  signal {s}" for s in contract.game_manager_signals)
        if contract.game_manager_signals
        else "  (none)",
        methods="\n".join(f"  {m}" for m in contract.game_manager_methods),
    )


async def _generate_method_bodies(
    client: AsyncAnthropic,
    contract: GameContract,
) -> dict[str, str]:
    """Call the LLM to generate method bodies for all contract methods.

    Returns a dict mapping method signature -> GDScript body string.
    """
    if not contract.game_manager_methods:
        return {}

    system_prompt = _build_method_gen_prompt(contract)
    user_message = (
        "Generate the method bodies for these GameManager methods:\n"
        + json.dumps(contract.game_manager_methods, indent=2)
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
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)

    # Extract JSON object via brace matching
    json_start = raw.find("{")
    if json_start >= 0:
        depth = 0
        for i, ch in enumerate(raw[json_start:], start=json_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    raw = raw[json_start : i + 1]
                    break

    bodies: dict[str, str] = json.loads(raw)
    return bodies


def _assemble_script(
    contract: GameContract,
    method_bodies: dict[str, str] | None = None,
) -> str:
    """Assemble the final game_manager.gd from template + contract + method bodies.

    Args:
        contract: The game contract.
        method_bodies: Optional dict mapping method signature -> body string.
            If None or missing a method, falls back to a pass stub.
    """
    if method_bodies is None:
        method_bodies = {}

    parts: list[str] = [_TEMPLATE_BASE]

    # --- Signals ---
    if contract.game_manager_signals:
        parts.append("\n# --- Game-specific signals ---")
        for sig in contract.game_manager_signals:
            parts.append(f"signal {sig}")

    # --- Enums (all from contract, including GameState) ---
    if contract.game_manager_enums:
        parts.append("\n# --- Game-specific enums ---")
        for name, variants in contract.game_manager_enums.items():
            parts.append(f"enum {name} {{ {', '.join(variants)} }}")

    # --- Properties ---
    if contract.game_manager_properties:
        parts.append("\n# --- Game-specific properties ---")
        for prop in contract.game_manager_properties:
            parts.append(f"var {prop}")

    # --- Methods (with real bodies or fallback stubs) ---
    # Filter out methods whose bare name duplicates a template base method
    contract_methods = [
        m for m in contract.game_manager_methods
        if _extract_method_name(m) not in _TEMPLATE_BASE_METHOD_NAMES
    ]
    if contract_methods:
        parts.append("\n# --- Game-specific methods ---")
        for method_sig in contract_methods:
            parts.append(f"func {method_sig}:")
            body = method_bodies.get(method_sig)
            if body:
                # Normalize body: ensure each line is tab-indented
                for line in body.splitlines():
                    stripped = line.strip()
                    if stripped:
                        # Count existing leading tabs, ensure at least one
                        if line.startswith("\t"):
                            parts.append(line)
                        else:
                            parts.append(f"\t{stripped}")
                    else:
                        parts.append("")
            else:
                parts.append("\tpass")

    # Ensure trailing newline
    result = "\n".join(parts)
    if not result.endswith("\n"):
        result += "\n"

    return result


def generate_game_manager_script(contract: GameContract) -> str:
    """Generate a game_manager.gd with stub methods (no LLM call).

    Synchronous fallback used by tests and when no LLM client is available.
    """
    return _assemble_script(contract, method_bodies=None)


async def generate_game_manager_script_async(
    client: AsyncAnthropic,
    contract: GameContract,
) -> str:
    """Generate a game_manager.gd with LLM-implemented method bodies.

    Calls the LLM once to generate all method bodies, then assembles
    the final script deterministically.
    """
    method_bodies = await _generate_method_bodies(client, contract)
    return _assemble_script(contract, method_bodies=method_bodies)
