"""Tripo API client — text-to-3D asset generation via the Tripo API.

Wraps the two-endpoint async flow (submit task, poll for result, download GLB)
using httpx directly to avoid an extra SDK dependency.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

TRIPO_BASE_URL = "https://api.tripo3d.ai/v2/openapi"
TRIPO_MODEL_VERSION = "P1-20260311"  # optimized for low-poly game assets

# Poll settings
POLL_INITIAL_DELAY = 2.0  # seconds
POLL_MAX_DELAY = 10.0
POLL_TIMEOUT = 200.0  # total seconds before giving up

TERMINAL_STATUSES = frozenset({"SUCCESS", "FAILED", "CANCELLED", "BANNED", "EXPIRED"})


class TripoError(Exception):
    """Raised when a Tripo API call fails."""


class TripoAssetGenerator:
    """Async wrapper around the Tripo text-to-3D API.

    Usage::

        gen = TripoAssetGenerator()
        glb_path = await gen.generate_3d_asset(
            prompt="A low-poly wooden treasure chest",
            dest=Path("project/assets/models/treasure_chest.glb"),
        )
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("TRIPO_API_KEY", "")
        if not self._api_key:
            raise TripoError("TRIPO_API_KEY not set")
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def generate_3d_asset(
        self,
        prompt: str,
        dest: Path,
        *,
        negative_prompt: str = "low quality, blurry, distorted",
    ) -> Path:
        """Generate a 3D model from text and save as GLB.

        Args:
            prompt: Description of the 3D model to generate.
            dest: Destination path for the .glb file.
            negative_prompt: Things to avoid in the generation.

        Returns:
            Path to the downloaded .glb file.

        Raises:
            TripoError: On API failure, timeout, or download error.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Submit task
            task_id = await self._submit_task(client, prompt, negative_prompt)
            logger.info("Tripo task submitted: %s (prompt: %.80s)", task_id, prompt)

            # Step 2: Poll until complete
            download_url = await self._poll_task(client, task_id)
            logger.info("Tripo task %s complete, downloading GLB", task_id)

            # Step 3: Download GLB
            dest.parent.mkdir(parents=True, exist_ok=True)
            await self._download_glb(client, download_url, dest)
            logger.info("Saved GLB to %s (%d bytes)", dest, dest.stat().st_size)

            return dest

    async def _submit_task(
        self,
        client: httpx.AsyncClient,
        prompt: str,
        negative_prompt: str,
    ) -> str:
        """POST /task to create a text_to_model task."""
        resp = await client.post(
            f"{TRIPO_BASE_URL}/task",
            headers=self._headers,
            json={
                "type": "text_to_model",
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "model_version": TRIPO_MODEL_VERSION,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise TripoError(f"Tripo submit failed: {data}")

        task_id = data["data"]["task_id"]
        return task_id

    async def _poll_task(self, client: httpx.AsyncClient, task_id: str) -> str:
        """Poll GET /task/{task_id} until terminal status. Returns GLB download URL."""
        delay = POLL_INITIAL_DELAY
        elapsed = 0.0

        while elapsed < POLL_TIMEOUT:
            resp = await client.get(
                f"{TRIPO_BASE_URL}/task/{task_id}",
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                raise TripoError(f"Tripo poll error: {data}")

            status = data["data"]["status"]
            logger.debug(
                "Tripo task %s status: %s (%.0fs elapsed)", task_id, status, elapsed
            )

            if status == "SUCCESS":
                # Extract GLB download URL from output
                output = data["data"].get("output", {})
                glb_url = output.get("model")
                if not glb_url:
                    raise TripoError(f"No GLB URL in successful task output: {output}")
                return glb_url

            if status in TERMINAL_STATUSES:
                raise TripoError(f"Tripo task {task_id} ended with status: {status}")

            await asyncio.sleep(delay)
            elapsed += delay
            delay = min(delay * 1.5, POLL_MAX_DELAY)

        raise TripoError(f"Tripo task {task_id} timed out after {POLL_TIMEOUT}s")

    async def _download_glb(
        self, client: httpx.AsyncClient, url: str, dest: Path
    ) -> None:
        """Download a GLB file from the given URL."""
        async with client.stream("GET", url, timeout=60.0) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=8192):
                    f.write(chunk)
