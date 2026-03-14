# click_to_move.gd
# Attach to a Node2D to make it move to the last mouse click position.

extends Node2D

@export var move_speed: float = 150.0   # Pixels per second
@export var arrival_threshold: float = 4.0  # Stops when within this distance

var _target_position: Vector2 = Vector2.ZERO
var _moving: bool = false

func _ready() -> void:
	_target_position = global_position

func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			_target_position = get_global_mouse_position()
			_moving = true

func _process(delta: float) -> void:
	if not _moving:
		return
	var direction: Vector2 = _target_position - global_position
	if direction.length() < arrival_threshold:
		global_position = _target_position
		_moving = false
		return
	global_position += direction.normalized() * move_speed * delta
