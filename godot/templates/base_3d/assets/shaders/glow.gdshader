shader_type canvas_item;

uniform float glow_strength: hint_range(0.0, 10.0) = 2.0;
uniform vec4 glow_color: source_color = vec4(1.0, 0.8, 0.2, 1.0);
uniform float glow_radius: hint_range(1.0, 8.0) = 3.0;

void fragment() {
	vec4 base_color = texture(TEXTURE, UV);
	float glow = 0.0;
	vec2 pixel = TEXTURE_PIXEL_SIZE;
	float samples = 0.0;
	for (float x = -glow_radius; x <= glow_radius; x += 1.0) {
		for (float y = -glow_radius; y <= glow_radius; y += 1.0) {
			glow += texture(TEXTURE, UV + vec2(x, y) * pixel).a;
			samples += 1.0;
		}
	}
	glow /= samples;
	vec4 glow_contrib = glow_color * glow_strength * glow;
	COLOR = base_color + vec4(glow_contrib.rgb * (1.0 - base_color.a), 0.0);
	COLOR.a = base_color.a;
}
