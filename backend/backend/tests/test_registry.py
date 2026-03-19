"""Tests for pipeline registry (PIPE-04)."""

from __future__ import annotations

import pytest

from backend.pipelines.contract.pipeline import ContractPipeline
from backend.pipelines.registry import PIPELINES, get_pipeline
from backend.pipelines.stub.pipeline import StubPipeline


def test_registry_resolves_stub():
    """PIPELINES["stub"] is StubPipeline."""
    assert PIPELINES["stub"] is StubPipeline


def test_contract_pipeline_in_registry():
    """get_pipeline("contract") returns ContractPipeline."""
    assert get_pipeline("contract") is ContractPipeline


def test_registry_get_pipeline_unknown_raises():
    """get_pipeline("unknown") raises KeyError."""
    with pytest.raises(KeyError):
        get_pipeline("nonexistent")


def test_agentic_pipeline_in_registry():
    """get_pipeline("agentic") returns AgenticPipeline."""
    from backend.pipelines.agentic.pipeline import AgenticPipeline

    assert get_pipeline("agentic") is AgenticPipeline


def test_agentic_satisfies_protocol():
    """AgenticPipeline has a generate method with correct signature."""
    import inspect

    from backend.pipelines.agentic.pipeline import AgenticPipeline

    assert hasattr(AgenticPipeline, "generate")
    sig = inspect.signature(AgenticPipeline.generate)
    params = list(sig.parameters.keys())
    assert "prompt" in params
    assert "job_id" in params
    assert "emit" in params
    assert "save_intermediate" in params
