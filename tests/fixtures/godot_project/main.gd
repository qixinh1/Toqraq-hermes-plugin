extends Node2D

var t := 0.0
@export var semantic_input_count := 0
@export var keyboard_input_count := 0
@export var pointer_input_count := 0
@export var gamepad_input_count := 0

func _ready() -> void:
	$TextInput.grab_focus()
	print("Toqraq fixture ready")

func _input(event: InputEvent) -> void:
	if event is InputEventAction and event.action == &"toqraq_test" and event.pressed:
		semantic_input_count += 1
	if event is InputEventKey and event.physical_keycode == KEY_A and event.pressed:
		keyboard_input_count += 1
	if event is InputEventMouseMotion:
		pointer_input_count += 1
	if event is InputEventJoypadMotion and event.axis == JOY_AXIS_LEFT_X:
		gamepad_input_count += 1

func _process(delta: float) -> void:
	t += delta
	queue_redraw()

func _draw() -> void:
	var size := get_viewport_rect().size
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.12, 0.14, 0.18))
	var center := size * 0.5
	var points := PackedVector2Array()
	for i in 5:
		var angle := t + TAU * i / 5.0
		points.append(center + Vector2(cos(angle), sin(angle)) * minf(size.x, size.y) * 0.3)
	draw_colored_polygon(points, Color(0.4, 0.7, 1.0))
	draw_string(
		ThemeDB.fallback_font,
		Vector2(16, 32),
		"fps=%d  size=%dx%d  t=%.1f" % [Engine.get_frames_per_second(), int(size.x), int(size.y), t],
		HORIZONTAL_ALIGNMENT_LEFT,
		-1,
		20,
		Color.WHITE,
	)
