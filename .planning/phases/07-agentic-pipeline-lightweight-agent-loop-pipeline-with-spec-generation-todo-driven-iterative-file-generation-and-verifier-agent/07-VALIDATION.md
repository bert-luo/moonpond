---
phase: 07
slug: agentic-pipeline-lightweight-agent-loop-pipeline-with-spec-generation-todo-driven-iterative-file-generation-and-verifier-agent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with pytest-anyio |
| **Config file** | `backend/pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `cd backend && uv run pytest backend/tests/test_agentic_pipeline.py backend/tests/test_agentic_models.py -x` |
| **Full suite command** | `cd backend && uv run pytest backend/tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest backend/tests/test_agentic_pipeline.py backend/tests/test_agentic_models.py -x`
- **After every plan wave:** Run `cd backend && uv run pytest backend/tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | AGNT-05 | unit | `pytest backend/tests/test_agentic_models.py -x` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | AGNT-06 | unit | `pytest backend/tests/test_agentic_models.py -x` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 1 | AGNT-02 | unit | `pytest backend/tests/test_agentic_pipeline.py::test_write_file_dispatch -x` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 1 | AGNT-03 | unit | `pytest backend/tests/test_agentic_pipeline.py::test_read_file_dispatch -x` | ❌ W0 | ⬜ pending |
| 07-02-03 | 02 | 1 | AGNT-04 | unit | `pytest backend/tests/test_agentic_pipeline.py::test_message_accumulation -x` | ❌ W0 | ⬜ pending |
| 07-03-01 | 03 | 2 | AGNT-07 | unit | `pytest backend/tests/test_agentic_pipeline.py::test_max_iterations_exit -x` | ❌ W0 | ⬜ pending |
| 07-03-02 | 03 | 2 | AGNT-08 | unit | `pytest backend/tests/test_registry.py -x` | ✅ extend | ⬜ pending |
| 07-03-03 | 03 | 2 | AGNT-09 | unit | `pytest backend/tests/test_agentic_pipeline.py::test_iteration_dirs -x` | ❌ W0 | ⬜ pending |
| 07-03-04 | 03 | 2 | AGNT-01 | unit | `pytest backend/tests/test_registry.py -x` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_agentic_pipeline.py` — stubs for AGNT-02, AGNT-03, AGNT-04, AGNT-07, AGNT-08, AGNT-09
- [ ] `backend/tests/test_agentic_models.py` — stubs for AGNT-05, AGNT-06
- [ ] Extend `backend/tests/test_registry.py` with `test_agentic_pipeline_in_registry` — AGNT-01

*All tests must mock `AsyncAnthropic.messages.create` using `AsyncMock` (following project pattern from `test_contract_generator.py`). No real LLM calls in tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end game generation | AGNT-08 | Requires live LLM + Godot export | Run `python scripts/generate.py --pipeline agentic` with real API key |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
