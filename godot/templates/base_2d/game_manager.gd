# game_manager.gd
# Autoloaded as GameManager — available globally to all generated scenes.
# The Visual Polisher pipeline stage sets the active palette by name.
# The Code Generator can access GameManager.get_palette_color(t) for any color needs.

extends Node

## Active color palette. Default: neon. Pipeline sets this before gameplay starts.
var active_palette: Gradient = null

## Game state for win/fail tracking. Generated scenes update this.
enum GameState { PLAYING, WON, LOST }
var state: GameState = GameState.PLAYING

func _ready() -> void:
	# Default palette: neon. Pipeline Visual Polisher overrides this.
	active_palette = load("res://assets/palettes/neon.tres")

## Set the active palette by name (matches filenames in assets/palettes/).
## Called by generated scene scripts when the Visual Polisher selects a palette.
func set_palette(palette_name: String) -> void:
	var path := "res://assets/palettes/%s.tres" % palette_name
	if ResourceLoader.exists(path):
		active_palette = load(path)
	else:
		push_warning("GameManager: palette not found: " + path)

## Sample the active palette at position t (0.0 to 1.0).
## Returns Color.WHITE if no palette is loaded.
func get_palette_color(t: float) -> Color:
	if active_palette:
		return active_palette.sample(clampf(t, 0.0, 1.0))
	return Color.WHITE

## Called by generated scenes to signal win/loss.
func set_state(new_state: GameState) -> void:
	state = new_state
