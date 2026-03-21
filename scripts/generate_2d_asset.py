#!/usr/bin/env python3
"""Standalone script to generate 2D game assets and display them in a popup.

Usage (run from backend/):
    # Single sprite
    uv run python ../scripts/generate_2d_asset.py "A pixel art sword, top-down RPG style"

    # Spritesheet — auto-detects animation type from prompt
    uv run python ../scripts/generate_2d_asset.py --spritesheet "A pixel art knight walk cycle"

    # Spritesheet — explicit animation preset
    uv run python ../scripts/generate_2d_asset.py --spritesheet --animation attack "A pixel art knight"

    # Spritesheet — custom frame count
    uv run python ../scripts/generate_2d_asset.py --spritesheet --num-frames 6 "A pixel art knight walk cycle"

    # With post-processing
    uv run python ../scripts/generate_2d_asset.py "A pixel art tree" --trim --resize 64 64

    # Save to file
    uv run python ../scripts/generate_2d_asset.py "A pixel art gem" -o gem.png
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure repo root's .env is loaded and backend is importable
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root / "backend"))

from dotenv import load_dotenv  # provided by python-dotenv in backend's venv

load_dotenv(_repo_root / ".env")

from backend.pipelines.agentic.image_gen_client import (
    AssetMode,
    ImageGenClient,
    PostProcessConfig,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate 2D game assets with OpenAI gpt-image-1")
    p.add_argument("prompt", help="Description of the asset to generate")
    p.add_argument("--output", "-o", type=Path, help="Save to file")
    p.add_argument("--model", default="gpt-image-1-mini")
    p.add_argument("--size", default="1024x1024", choices=["1024x1024", "1536x1024", "1024x1536"])
    p.add_argument("--quality", default="medium", choices=["low", "medium", "high"])

    # Spritesheet mode
    sp = p.add_argument_group("spritesheet")
    sp.add_argument("--spritesheet", action="store_true", help="Generate a spritesheet")
    sp.add_argument("--animation", help="Animation type hint (e.g. 'walk', 'attack', 'idle')")
    sp.add_argument("--num-frames", type=int, help="Override frame count")
    sp.add_argument("--columns", type=int, help="Spritesheet columns (default: all in one row)")

    # Post-processing
    pp = p.add_argument_group("post-processing")
    pp.add_argument("--trim", action="store_true", help="Auto-crop transparent padding")
    pp.add_argument("--resize", type=int, nargs=2, metavar=("W", "H"), help="Resize to WxH")
    pp.add_argument("--quantize", type=int, metavar="N", help="Reduce to N colors")
    pp.add_argument("--no-display", action="store_true", help="Skip popup display")

    return p.parse_args()


async def main() -> None:
    args = parse_args()

    pp = PostProcessConfig(
        trim=args.trim,
        target_size=tuple(args.resize) if args.resize else None,
        quantize_colors=args.quantize,
    )

    client = ImageGenClient(model=args.model)

    if args.spritesheet:
        anim_label = args.animation or "(auto-detect)"
        print(f"Generating spritesheet: animation={anim_label}...")
        asset = await client.generate_spritesheet(
            prompt=args.prompt,
            dest=args.output,
            animation=args.animation,
            num_frames=args.num_frames,
            size=args.size,
            quality=args.quality,
            columns=args.columns,
            post_process=pp,
        )
    else:
        print(f"Generating single asset...")
        asset = await client.generate(
            prompt=args.prompt,
            dest=args.output,
            size=args.size,
            quality=args.quality,
            post_process=pp,
        )

    print(f"Done! Mode: {asset.mode.value}, Frames: {asset.frame_count}, "
          f"Size: {asset.image.width}x{asset.image.height}")

    if args.output:
        print(f"Saved to {args.output}")

    if not args.no_display:
        _display(asset)


def _display(asset) -> None:
    """Show the generated asset in a matplotlib popup window."""
    try:
        import matplotlib
        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available, trying PIL show() fallback...")
        asset.image.show()
        return

    if asset.mode == AssetMode.SPRITESHEET and asset.frames:
        n = len(asset.frames)
        fig, axes = plt.subplots(1, n + 1, figsize=(3 * (n + 1), 4))
        for i, frame in enumerate(asset.frames):
            axes[i].imshow(frame)
            axes[i].set_title(f"Frame {i}")
            axes[i].axis("off")
        axes[-1].imshow(asset.image)
        axes[-1].set_title("Spritesheet")
        axes[-1].axis("off")
        fig.suptitle(f"Spritesheet: {asset.prompt}", fontsize=11)
    else:
        fig, ax = plt.subplots(1, 1, figsize=(6, 6))
        ax.imshow(asset.image)
        ax.set_title(asset.prompt, fontsize=11)
        ax.axis("off")

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    asyncio.run(main())
