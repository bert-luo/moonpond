"""In-memory job state store.

Queue instances are created inside async handlers (not at module level)
to avoid RuntimeError from creating a Queue outside a running event loop.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # ProgressEvent import kept here to avoid circular deps

active_jobs: dict[str, asyncio.Queue] = {}
"""Map of job_id -> asyncio.Queue holding ProgressEvent objects."""
