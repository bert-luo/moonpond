---
phase: 2
slug: backend-pipeline-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-anyio |
| **Config file** | `backend/pyproject.toml [tool.pytest.ini_options]` — Wave 0 installs |
| **Quick run command** | `uv run pytest backend/tests/ -x -q` |
| **Full suite command** | `uv run pytest backend/tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest backend/tests/ -x -q`
- **After every plan wave:** Run `uv run pytest backend/tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | PIPE-01 | unit | `uv run pytest backend/tests/test_generate.py::test_generate_returns_job_id -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0 | PIPE-01 | unit | `uv run pytest backend/tests/test_generate.py::test_job_id_is_uuid -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 0 | PIPE-02 | unit | `uv run pytest backend/tests/test_stream.py::test_stream_content_type -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 0 | PIPE-02 | unit | `uv run pytest backend/tests/test_stream.py::test_stream_yields_events -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 0 | PIPE-03 | integration | `uv run pytest backend/tests/test_static.py::test_static_file_served -x` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 0 | PIPE-04 | unit | `uv run pytest backend/tests/test_registry.py::test_registry_resolves_stub -x` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 0 | PIPE-04 | unit | `uv run pytest backend/tests/test_generate.py::test_pipeline_query_param -x` | ❌ W0 | ⬜ pending |
| 02-05-01 | 05 | 0 | PIPE-05 | unit | `uv run pytest backend/tests/test_runner.py::test_runner_validates_file_not_exit_code -x` | ❌ W0 | ⬜ pending |
| 02-05-02 | 05 | 0 | PIPE-05 | unit | `uv run pytest backend/tests/test_runner.py::test_runner_captures_stderr -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/__init__.py` — marks tests as package
- [ ] `backend/tests/test_generate.py` — stubs for PIPE-01
- [ ] `backend/tests/test_stream.py` — stubs for PIPE-02
- [ ] `backend/tests/test_static.py` — stubs for PIPE-03
- [ ] `backend/tests/test_registry.py` — stubs for PIPE-04
- [ ] `backend/tests/test_runner.py` — stubs for PIPE-05 (mock subprocess for unit tests)
- [ ] `backend/pyproject.toml` — pytest config with anyio mode
- [ ] Framework install: `uv add --dev pytest pytest-anyio httpx anyio`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SSE heartbeat every 15s | PIPE-02 | Timing-sensitive, impractical in fast tests | Open `/api/stream/{job_id}` in browser devtools, verify heartbeat comments arrive every ~15s |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
