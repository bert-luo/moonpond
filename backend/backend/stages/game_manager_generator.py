"""Game Manager GDScript generator -- produces a game-specific game_manager.gd from a GameContract.

Takes the static template base (palette, state management) and extends it with
contract-specified enums, properties, methods, and signals so that node generators
can reference a concrete GameManager API instead of hallucinating one.
"""

from __future__ import annotations

from backend.stages.contract_models import GameContract

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

## Game state for win/fail tracking. Generated scenes update this.
enum GameState { PLAYING, WON, LOST }
var state: GameState = GameState.PLAYING

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

## Called by generated scenes to signal win/loss.
func set_state(new_state: GameState) -> void:
\tstate = new_state
'''


def generate_game_manager_script(contract: GameContract) -> str:
    """Generate a game-specific game_manager.gd from a GameContract.

    The output preserves the static template base (palette, state management)
    and appends contract-specified signals, enums, properties, and method stubs.

    Args:
        contract: The game contract defining the GameManager API extensions.

    Returns:
        A complete GDScript string for game_manager.gd.
    """
    parts: list[str] = [_TEMPLATE_BASE]

    # --- Signals ---
    if contract.game_manager_signals:
        parts.append("\n# --- Game-specific signals ---")
        for sig in contract.game_manager_signals:
            parts.append(f"signal {sig}")

    # --- Enums (skip GameState -- already in base) ---
    extra_enums = {
        k: v
        for k, v in contract.game_manager_enums.items()
        if k != "GameState"
    }
    if extra_enums:
        parts.append("\n# --- Game-specific enums ---")
        for name, variants in extra_enums.items():
            parts.append(f"enum {name} {{ {', '.join(variants)} }}")

    # --- Properties ---
    if contract.game_manager_properties:
        parts.append("\n# --- Game-specific properties ---")
        for prop in contract.game_manager_properties:
            parts.append(f"var {prop}")

    # --- Method stubs ---
    if contract.game_manager_methods:
        parts.append("\n# --- Game-specific methods ---")
        for method_sig in contract.game_manager_methods:
            # method_sig is e.g. "add_currency(amount: int)" or "can_afford(cost: int) -> bool"
            if " -> " in method_sig:
                parts.append(f"func {method_sig}:")
            else:
                parts.append(f"func {method_sig}:")
            parts.append("\tpass")

    # Ensure trailing newline
    result = "\n".join(parts)
    if not result.endswith("\n"):
        result += "\n"

    return result
