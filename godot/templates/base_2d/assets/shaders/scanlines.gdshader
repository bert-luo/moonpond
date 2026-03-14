shader_type canvas_item;

uniform float line_count: hint_range(50.0, 800.0) = 200.0;
uniform float opacity: hint_range(0.0, 1.0) = 0.3;
uniform vec4 line_color: source_color = vec4(0.0, 0.0, 0.0, 1.0);

void fragment() {
	vec4 base_color = texture(TEXTURE, UV);
	float line = step(0.5, fract(UV.y * line_count));
	vec4 scanline = mix(base_color, line_color, line * opacity);
	COLOR = scanline;
	COLOR.a = base_color.a;
}
