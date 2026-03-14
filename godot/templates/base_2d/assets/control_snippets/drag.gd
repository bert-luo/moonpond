# drag.gd
# Attach to a Node2D to make it draggable with the mouse.
# The node must have a CollisionShape2D sibling or parent for click detection,
# OR override _is_point_inside() for custom hit testing.

extends Node2D

@export var drag_z_index: int = 10  # Z-index while being dragged

var _dragging: bool = false
var _drag_offset: Vector2 = Vector2.ZERO
var _original_z_index: int = 0

func _ready() -> void:
	_original_z_index = z_index

func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_LEFT:
			if mb.pressed:
				var local_pos: Vector2 = to_local(get_global_mouse_position())
				# Simple rectangular hit check -- override for custom shapes
				if _is_point_inside(local_pos):
					_dragging = true
					_drag_offset = global_position - get_global_mouse_position()
					z_index = drag_z_index
			else:
				if _dragging:
					_dragging = false
					z_index = _original_z_index

func _process(_delta: float) -> void:
	if _dragging:
		global_position = get_global_mouse_position() + _drag_offset

## Override this in subclasses for non-rectangular hit detection.
func _is_point_inside(local_pos: Vector2) -> bool:
	# Default: accept any click (useful for testing; override with actual bounds)
	return true
