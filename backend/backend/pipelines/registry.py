"""Pipeline registry mapping strategy names to pipeline classes.

The registry starts empty.  Pipeline implementations register themselves
here (e.g., the stub pipeline added in Plan 02-02).
"""

from __future__ import annotations

from .multi_stage.pipeline import MultiStagePipeline
from .stub.pipeline import StubPipeline

PIPELINES: dict[str, type] = {"stub": StubPipeline, "multi_stage": MultiStagePipeline}
"""Map of strategy name -> pipeline class satisfying GamePipeline Protocol."""


def get_pipeline(name: str) -> type:
    """Look up a pipeline class by strategy name.

    Raises:
        KeyError: If *name* is not registered, with a message listing
            the available pipelines.
    """
    try:
        return PIPELINES[name]
    except KeyError:
        available = ", ".join(sorted(PIPELINES)) or "(none)"
        raise KeyError(
            f"Unknown pipeline '{name}'. Available pipelines: {available}"
        ) from None
