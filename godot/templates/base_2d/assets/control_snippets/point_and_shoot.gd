# point_and_shoot.gd
# Attach to a Node2D to rotate it toward the mouse and shoot on left-click.
# Set projectile_scene to a PackedScene with a Node2D root and a velocity var.

extends Node2D

@export var rotation_speed: float = 0.0    # 0.0 = instant; > 0 = smooth rotation (radians/sec)
@export var projectile_scene: PackedScene = null  # Assign the projectile PackedScene
@export var projectile_speed: float = 400.0
@export var fire_cooldown: float = 0.2     # Seconds between shots

var _cooldown_remaining: float = 0.0

func _process(delta: float) -> void:
	_cooldown_remaining = maxf(0.0, _cooldown_remaining - delta)
	_rotate_toward_mouse(delta)

func _input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			_try_fire()

func _rotate_toward_mouse(delta: float) -> void:
	var target_angle: float = get_global_mouse_position().angle_to_point(global_position) + PI
	if rotation_speed <= 0.0:
		rotation = target_angle
	else:
		rotation = lerp_angle(rotation, target_angle, rotation_speed * delta)

func _try_fire() -> void:
	if _cooldown_remaining > 0.0:
		return
	if projectile_scene == null:
		push_warning("point_and_shoot: projectile_scene not set")
		return
	_cooldown_remaining = fire_cooldown
	var projectile: Node2D = projectile_scene.instantiate() as Node2D
	if projectile == null:
		return
	projectile.global_position = global_position
	projectile.rotation = rotation
	# Set velocity if the projectile has one
	if "velocity" in projectile:
		projectile.velocity = Vector2.RIGHT.rotated(rotation) * projectile_speed
	get_parent().add_child(projectile)
