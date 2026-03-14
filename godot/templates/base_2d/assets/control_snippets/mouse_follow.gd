# mouse_follow.gd
# Attach to a Node2D to make it smoothly follow the mouse cursor.
# Usage: set as script on any Node2D, or use preload().new() and add_child()

extends Node2D

@export var follow_speed: float = 8.0  # Units per second; higher = faster tracking

func _process(delta: float) -> void:
	var target: Vector2 = get_global_mouse_position()
	global_position = global_position.lerp(target, clampf(follow_speed * delta, 0.0, 1.0))
