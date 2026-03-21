"""OpenAI image generation client — 2D game asset and spritesheet generation.

Generates individual sprites or multi-frame spritesheets using the OpenAI
gpt-image-1 API with parametric post-processing (trim, resize, palette
quantization) via Pillow.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import json

from openai import AsyncOpenAI
from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-image-1-mini"
MAX_SPRITESHEET_FRAMES = 8
ASSET_BUDGET = 20  # max assets per game


class AssetMode(str, Enum):
    SINGLE = "single"
    SPRITESHEET = "spritesheet"


@dataclass
class PostProcessConfig:
    """Parametric post-processing options applied after generation."""

    trim: bool = True  # auto-crop transparent padding
    target_size: tuple[int, int] | None = None  # resize to (w, h) if set
    quantize_colors: int | None = None  # reduce to N colors if set


@dataclass
class GeneratedAsset:
    """Result of a single or spritesheet generation."""

    image: Image.Image
    mode: AssetMode
    frame_count: int = 1
    frame_size: tuple[int, int] = (0, 0)
    prompt: str = ""
    frames: list[Image.Image] = field(default_factory=list)


class ImageGenError(Exception):
    """Raised when image generation fails."""


class ImageGenClient:
    """Async 2D asset generator using OpenAI gpt-image-1 API.

    Usage::

        gen = ImageGenClient()

        # Single sprite
        asset = await gen.generate(
            prompt="A pixel art treasure chest, 32x32, top-down view",
            dest=Path("assets/sprites/chest.png"),
        )

        # Spritesheet — auto-detects "walk" preset from prompt
        asset = await gen.generate_spritesheet(
            prompt="A pixel art knight walk cycle",
            dest=Path("assets/sprites/knight_walk.png"),
        )

        # Spritesheet — explicit preset override
        asset = await gen.generate_spritesheet(
            prompt="A pixel art knight",
            animation="attack",
            dest=Path("assets/sprites/knight_attack.png"),
        )
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self._api_key:
            raise ImageGenError("OPENAI_API_KEY not set")
        self._client = AsyncOpenAI(api_key=self._api_key)
        self._model = model

    async def generate(
        self,
        prompt: str,
        dest: Path | None = None,
        *,
        size: str = "1024x1024",
        quality: str = "medium",
        post_process: PostProcessConfig | None = None,
    ) -> GeneratedAsset:
        """Generate a single 2D asset with transparent background.

        Args:
            prompt: Description of the sprite to generate.
            dest: Optional path to save the PNG.
            size: Image dimensions (1024x1024, 1536x1024, 1024x1536).
            quality: Generation quality (low, medium, high).
            post_process: Optional post-processing config.

        Returns:
            GeneratedAsset with the final image.
        """
        # Infer style-based post-processing and merge with caller config
        post_process = await self._resolve_post_process(prompt, post_process)

        full_prompt = self._build_prompt(prompt)
        logger.info(
            "Generating single asset: %.80s (model=%s)", full_prompt, self._model
        )

        image = await self._call_api(full_prompt, size=size, quality=quality)

        if post_process:
            image = self._post_process(image, post_process)

        if dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            image.save(dest, "PNG")
            logger.info("Saved asset to %s", dest)

        return GeneratedAsset(
            image=image,
            mode=AssetMode.SINGLE,
            frame_count=1,
            frame_size=(image.width, image.height),
            prompt=prompt,
            frames=[image],
        )

    async def generate_spritesheet(
        self,
        prompt: str,
        dest: Path | None = None,
        *,
        animation: str | None = None,
        frame_prompts: list[str] | None = None,
        num_frames: int | None = None,
        size: str = "1024x1024",
        quality: str = "medium",
        columns: int | None = None,
        post_process: PostProcessConfig | None = None,
        max_reference_frames: int = 2,
    ) -> GeneratedAsset:
        """Generate a spritesheet by creating consistent frames sequentially.

        Frame descriptions are resolved in priority order:
        1. Explicit ``frame_prompts`` if provided.
        2. ``animation`` preset name (e.g. "walk", "attack", "idle").
        3. Auto-detected from keywords in ``prompt`` (e.g. "knight walk cycle").
        4. Falls back to generic numbered frames.

        Frame 0 is generated from scratch. Each subsequent frame is generated
        via the images.edit API with the previous frame(s) as reference images,
        ensuring visual consistency across the spritesheet.

        Args:
            prompt: Description of the character/object (and optionally animation).
            dest: Optional path to save the spritesheet PNG.
            animation: Optional animation type hint for LLM decomposition.
            frame_prompts: Explicit per-frame descriptions (skips LLM).
            num_frames: Override frame count (default 4, max 6).
            size: Size for each individual frame generation.
            quality: Generation quality.
            columns: Number of columns in the sheet (default: all in one row).
            post_process: Post-processing applied to each frame before compositing.
            max_reference_frames: Max prior frames to pass as reference (1-3).

        Returns:
            GeneratedAsset with the composited spritesheet.
        """
        # Infer style-based post-processing and merge with caller config
        post_process = await self._resolve_post_process(prompt, post_process)

        # Resolve frame descriptions (LLM-powered decomposition)
        resolved_frames = await self._resolve_frame_prompts(
            prompt,
            animation=animation,
            frame_prompts=frame_prompts,
            num_frames=num_frames,
        )
        n_frames = min(len(resolved_frames), MAX_SPRITESHEET_FRAMES)
        resolved_frames = resolved_frames[:n_frames]
        cols = columns or n_frames
        rows = (n_frames + cols - 1) // cols

        logger.info(
            "Generating spritesheet: %d frames, %dx%d grid (model=%s)",
            n_frames,
            cols,
            rows,
            self._model,
        )

        logger.info("Resolved frame descriptions: %s", resolved_frames)

        valid_frames: list[Image.Image] = []

        for i, frame_desc in enumerate(resolved_frames):
            if i == 0:
                # First frame: generate from scratch
                full_prompt = self._build_spritesheet_frame_prompt(
                    prompt,
                    frame_desc,
                    i,
                    n_frames,
                )
                frame = await self._call_api(full_prompt, size=size, quality=quality)
            else:
                # Subsequent frames: use edit API with prior frames as reference
                reference_imgs = valid_frames[-max_reference_frames:]
                edit_prompt = self._build_spritesheet_edit_prompt(
                    prompt,
                    frame_desc,
                    i,
                    n_frames,
                )
                frame = await self._call_edit_api(
                    edit_prompt,
                    reference_images=reference_imgs,
                    size=size,
                    quality=quality,
                )
            logger.info("Frame %d/%d generated", i + 1, n_frames)
            valid_frames.append(frame)

        # Post-process individual frames
        if post_process:
            valid_frames = [self._post_process(f, post_process) for f in valid_frames]

        # Normalize frame sizes (use first frame as reference)
        frame_w, frame_h = valid_frames[0].size
        normalized = []
        for f in valid_frames:
            if f.size != (frame_w, frame_h):
                f = f.resize((frame_w, frame_h), Image.LANCZOS)
            normalized.append(f)

        # Composite into spritesheet
        sheet_w = cols * frame_w
        sheet_h = rows * frame_h
        sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

        for idx, frame in enumerate(normalized):
            col = idx % cols
            row = idx // cols
            sheet.paste(frame, (col * frame_w, row * frame_h))

        if dest:
            dest.parent.mkdir(parents=True, exist_ok=True)
            sheet.save(dest, "PNG")
            logger.info(
                "Saved spritesheet to %s (%dx%d, %d frames)",
                dest,
                sheet_w,
                sheet_h,
                n_frames,
            )

        return GeneratedAsset(
            image=sheet,
            mode=AssetMode.SPRITESHEET,
            frame_count=n_frames,
            frame_size=(frame_w, frame_h),
            prompt=prompt,
            frames=normalized,
        )

    # ── Frame resolution ────────────────────────────────────────────────

    async def _resolve_frame_prompts(
        self,
        prompt: str,
        *,
        animation: str | None = None,
        frame_prompts: list[str] | None = None,
        num_frames: int | None = None,
    ) -> list[str]:
        """Resolve frame descriptions — uses LLM to decompose the animation.

        Priority:
        1. Explicit ``frame_prompts`` if provided.
        2. LLM decomposition of the prompt + optional animation hint.
        3. Generic numbered frames as last resort.
        """
        if frame_prompts:
            frames = list(frame_prompts)
            if num_frames and len(frames) < num_frames:
                for i in range(len(frames), num_frames):
                    frames.append(f"animation frame {i + 1}")
            return frames[:num_frames] if num_frames else frames

        n = num_frames or 4
        n = min(n, 6)

        try:
            frames = await self._llm_decompose_frames(
                prompt, animation=animation, num_frames=n
            )
            if frames and len(frames) >= 2:
                logger.info("LLM decomposed animation into %d frames", len(frames))
                return frames
        except Exception as e:
            logger.warning("LLM frame decomposition failed: %s", e)

        return [f"animation frame {i + 1}" for i in range(n)]

    async def _llm_decompose_frames(
        self,
        prompt: str,
        *,
        animation: str | None = None,
        num_frames: int = 4,
    ) -> list[str]:
        """Ask a fast cheap LLM to break an animation prompt into frame descriptions."""
        anim_hint = f" The animation type is: {animation}." if animation else ""
        system = (
            "You decompose animation prompts into individual frame descriptions for a sprite sheet. "
            "Each frame description should describe the exact pose/position for that frame. "
            "Keep descriptions concise (under 15 words each). "
            "Return ONLY a JSON array of strings, no other text."
        )
        user_msg = (
            f"Break this into exactly {num_frames} animation frames:\n"
            f'"{prompt}"{anim_hint}\n\n'
            f"Return a JSON array of {num_frames} frame description strings."
        )

        resp = await self._client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=300,
        )

        text = resp.choices[0].message.content.strip()
        # Parse JSON array from response (handle markdown fences)
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        frames = json.loads(text)
        if not isinstance(frames, list) or not all(isinstance(f, str) for f in frames):
            raise ValueError(f"Expected list of strings, got: {type(frames)}")
        return frames

    # ── Style-based post-process inference ─────────────────────────────────

    async def _resolve_post_process(
        self,
        prompt: str,
        caller_config: PostProcessConfig | None,
    ) -> PostProcessConfig:
        """Merge caller-provided config with LLM-inferred style post-processing.

        Caller-provided fields (e.g. target_size from the game-gen LLM) take
        precedence.  Style fields (outline, quantize_colors) are inferred from
        the prompt by gpt-4o-mini when not already set by the caller.
        """
        inferred = await self._infer_style_post_process(prompt)

        if caller_config is None:
            return inferred

        # Merge: caller wins for target_size, inferred wins for style fields
        return PostProcessConfig(
            trim=caller_config.trim,
            target_size=caller_config.target_size or inferred.target_size,
            quantize_colors=caller_config.quantize_colors or inferred.quantize_colors,
        )

    async def _infer_style_post_process(self, prompt: str) -> PostProcessConfig:
        """Ask gpt-4o-mini to infer post-processing params from the asset prompt."""
        system = (
            "You analyze 2D game sprite prompts and recommend post-processing settings. "
            "Return ONLY a JSON object with these optional fields:\n"
            '- "quantize_colors": integer or null — number of colors for palette reduction '
            "(e.g. 16-32 for pixel art, 48-64 for retro, null for painterly/realistic styles)\n"
            "Be conservative: only set values when the art style clearly calls for them. "
            "Most modern/cartoon/colorful styles should get no quantization."
        )
        user_msg = f'Sprite prompt: "{prompt}"\n\nReturn JSON object with post-processing recommendations.'

        try:
            resp = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.0,
                max_tokens=100,
            )

            text = resp.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            data = json.loads(text)

            quantize = data.get("quantize_colors")
            if quantize is not None:
                quantize = max(8, min(int(quantize), 256))

            config = PostProcessConfig(
                trim=True,
                quantize_colors=quantize,
            )
            logger.info(
                "Inferred post-process for '%.60s': quantize=%s",
                prompt,
                quantize,
            )
            return config
        except Exception as e:
            logger.warning("Style post-process inference failed: %s", e)
            return PostProcessConfig(trim=True)

    # ── API call ──────────────────────────────────────────────────────────

    async def _call_api(
        self,
        prompt: str,
        *,
        size: str = "1024x1024",
        quality: str = "medium",
    ) -> Image.Image:
        """Call OpenAI image generation API and return a PIL Image."""
        try:
            result = await self._client.images.generate(
                model=self._model,
                prompt=prompt,
                size=size,
                quality=quality,
                output_format="png",
                background="transparent",
                n=1,
            )
        except Exception as e:
            raise ImageGenError(f"OpenAI image generation failed: {e}") from e

        b64_data = result.data[0].b64_json
        if not b64_data:
            raise ImageGenError("No image data returned from API")

        try:
            image_bytes = base64.b64decode(b64_data)
        except Exception as e:
            raise ImageGenError(f"Failed to decode image data: {e}") from e
        return Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    async def _call_edit_api(
        self,
        prompt: str,
        reference_images: list[Image.Image],
        *,
        size: str = "1024x1024",
        quality: str = "medium",
    ) -> Image.Image:
        """Call OpenAI images.edit API with reference images for consistency.

        Passes prior frames as input images so the model maintains the same
        character design, proportions, and palette.
        """
        # Convert PIL images to (filename, bytes, mime) tuples for the SDK
        image_files = []
        for i, img in enumerate(reference_images):
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            image_files.append((f"frame_{i}.png", buf.getvalue(), "image/png"))

        try:
            result = await self._client.images.edit(
                model=self._model,
                image=image_files if len(image_files) > 1 else image_files[0],
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
            )
        except Exception as e:
            raise ImageGenError(f"OpenAI image edit failed: {e}") from e

        b64_data = result.data[0].b64_json
        if not b64_data:
            raise ImageGenError("No image data returned from edit API")

        try:
            image_bytes = base64.b64decode(b64_data)
        except Exception as e:
            raise ImageGenError(f"Failed to decode image data: {e}") from e
        return Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    # ── Prompt engineering ────────────────────────────────────────────────

    @staticmethod
    def _build_prompt(user_prompt: str) -> str:
        """Wrap user prompt with game-asset-specific instructions."""
        return (
            f"{user_prompt}. "
            "Style: 2D game sprite with transparent background. "
            "Clean edges, no anti-aliasing artifacts against the background. "
            "Centered in frame with minimal padding."
        )

    @staticmethod
    def _build_spritesheet_frame_prompt(
        base_prompt: str,
        frame_desc: str,
        frame_idx: int,
        total_frames: int,
    ) -> str:
        """Build a prompt for the first frame of a spritesheet (no reference)."""
        return (
            f"{base_prompt}, {frame_desc}. "
            f"This is frame {frame_idx + 1} of {total_frames} in an animation sequence. "
            "Style: 2D game sprite with transparent background. "
            "Clean edges, no anti-aliasing artifacts. Centered in frame."
        )

    @staticmethod
    def _build_spritesheet_edit_prompt(
        base_prompt: str,
        frame_desc: str,
        frame_idx: int,
        total_frames: int,
    ) -> str:
        """Build a prompt for subsequent frames that receive prior frames as reference."""
        return (
            f"Generate a new animation frame: {frame_desc}. "
            f"This is frame {frame_idx + 1} of {total_frames} for: {base_prompt}. "
            "The provided reference image(s) show the previous frame(s) of this animation. "
            "You MUST use the EXACT same character design, proportions, color palette, "
            "art style, and level of detail as the reference. "
            "Only change the pose/position to match the frame description. "
            "Transparent background, clean edges, centered in frame."
        )

    # ── Post-processing ───────────────────────────────────────────────────

    @staticmethod
    def _post_process(image: Image.Image, config: PostProcessConfig) -> Image.Image:
        """Apply parametric post-processing to a generated image."""
        img = image.copy()

        # Trim transparent padding
        if config.trim:
            img = _trim_transparent(img)

        # Resize
        if config.target_size:
            img = img.resize(config.target_size, Image.LANCZOS)

        # Color quantization
        if config.quantize_colors:
            img = _quantize(img, config.quantize_colors)

        return img


# ── Post-processing helpers ──────────────────────────────────────────────


def _trim_transparent(img: Image.Image) -> Image.Image:
    """Crop to the bounding box of non-transparent pixels."""
    if img.mode != "RGBA":
        return img
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return img  # fully transparent, nothing to trim
    return img.crop(bbox)


def _quantize(img: Image.Image, n_colors: int) -> Image.Image:
    """Reduce image to N colors while preserving transparency."""
    if img.mode != "RGBA":
        return img

    # Separate alpha channel
    alpha = img.getchannel("A")

    # Quantize RGB only
    rgb = img.convert("RGB")
    quantized = rgb.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
    quantized_rgb = quantized.convert("RGB")

    # Recombine with original alpha
    result = quantized_rgb.convert("RGBA")
    result.putalpha(alpha)
    return result
