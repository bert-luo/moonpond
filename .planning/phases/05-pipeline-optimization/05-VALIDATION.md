---
phase: 5
slug: pipeline-optimization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-17
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-anyio |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `cd backend && uv run pytest tests/ -x -q --timeout=10` |
| **Full suite command** | `cd backend && uv run pytest tests/ -v --timeout=30` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/ -x -q --timeout=10`
- **After every plan wave:** Run `cd backend && uv run pytest tests/ -v --timeout=30`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | GameContract model | unit | `uv run pytest tests/test_contract.py -v` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | Pipeline class | unit | `uv run pytest tests/test_parallel_pipeline.py -v` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | Spec expander stage | unit | `uv run pytest tests/test_spec_expander.py -v` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 1 | Contract generator stage | unit | `uv run pytest tests/test_contract_generator.py -v` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 2 | Parallel node generation | unit | `uv run pytest tests/test_node_generator.py -v` | ❌ W0 | ⬜ pending |
| 05-03-02 | 03 | 2 | Wiring stage | unit | `uv run pytest tests/test_wiring.py -v` | ❌ W0 | ⬜ pending |
| 05-04-01 | 04 | 3 | End-to-end pipeline | integration | `uv run pytest tests/test_parallel_pipeline_e2e.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_contract.py` — stubs for GameContract model validation
- [ ] `tests/test_parallel_pipeline.py` — stubs for pipeline orchestration
- [ ] `tests/test_spec_expander.py` — stubs for spec expander stage
- [ ] `tests/test_contract_generator.py` — stubs for contract generator stage
- [ ] `tests/test_node_generator.py` — stubs for parallel node generation
- [ ] `tests/test_wiring.py` — stubs for wiring file generation
- [ ] `tests/test_parallel_pipeline_e2e.py` — stubs for end-to-end integration

*Existing infrastructure covers test framework — only test files needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Generated game runs in Godot | End-to-end quality | Requires Godot binary + visual inspection | Export WASM, load in browser, verify gameplay |
| No wiring bugs in output | Contract enforcement | Requires scene tree inspection | Check Main.tscn ExtResource refs match actual scripts |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
