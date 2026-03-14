shader_type canvas_item;

uniform float wave_amplitude: hint_range(0.0, 20.0) = 5.0;
uniform float wave_frequency: hint_range(0.0, 20.0) = 5.0;
uniform float wave_speed: hint_range(0.0, 10.0) = 2.0;

void fragment() {
	vec2 uv = UV;
	uv.x += sin(uv.y * wave_frequency + TIME * wave_speed) * wave_amplitude * TEXTURE_PIXEL_SIZE.x;
	uv.y += cos(uv.x * wave_frequency + TIME * wave_speed) * wave_amplitude * TEXTURE_PIXEL_SIZE.y;
	COLOR = texture(TEXTURE, uv);
}
