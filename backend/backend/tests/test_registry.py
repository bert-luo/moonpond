"""Tests for pipeline registry (PIPE-04)."""

from __future__ import annotations

import pytest

from backend.pipelines.registry import PIPELINES, get_pipeline
from backend.pipelines.stub.pipeline import StubPipeline


def test_registry_resolves_stub():
    """PIPELINES["stub"] is StubPipeline."""
    assert PIPELINES["stub"] is StubPipeline


def test_registry_get_pipeline_unknown_raises():
    """get_pipeline("unknown") raises KeyError."""
    with pytest.raises(KeyError):
        get_pipeline("nonexistent")
