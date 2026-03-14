shader_type canvas_item;

uniform float pixel_size: hint_range(1.0, 64.0) = 4.0;

void fragment() {
	vec2 uv = floor(UV / pixel_size) * pixel_size;
	COLOR = texture(TEXTURE, uv);
}
