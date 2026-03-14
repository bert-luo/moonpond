shader_type canvas_item;

uniform float aberration_strength: hint_range(0.0, 20.0) = 2.0;

void fragment() {
	vec2 offset = TEXTURE_PIXEL_SIZE * aberration_strength;
	float r = texture(TEXTURE, UV + vec2(offset.x, 0.0)).r;
	float g = texture(TEXTURE, UV).g;
	float b = texture(TEXTURE, UV - vec2(offset.x, 0.0)).b;
	float a = texture(TEXTURE, UV).a;
	COLOR = vec4(r, g, b, a);
}
