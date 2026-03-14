---
phase: 3
slug: multi-stage-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `cd backend && uv run pytest -x -q` |
| **Full suite command** | `cd backend && uv run pytest -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest -x -q`
- **After every plan wave:** Run `cd backend && uv run pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | STAGE-01 | unit | `cd backend && uv run pytest backend/tests/test_prompt_enhancer.py -v` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | STAGE-02 | unit | `cd backend && uv run pytest backend/tests/test_game_designer.py -v` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | STAGE-03 | unit | `cd backend && uv run pytest backend/tests/test_code_generator.py -v` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | STAGE-04 | unit | `cd backend && uv run pytest backend/tests/test_visual_polisher.py -v` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 2 | STAGE-05 | integration | `cd backend && uv run pytest backend/tests/test_exporter.py -v` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 2 | STAGE-06 | integration | `cd backend && uv run pytest backend/tests/test_multi_stage.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_prompt_enhancer.py` — stubs for STAGE-01
- [ ] `backend/tests/test_game_designer.py` — stubs for STAGE-02
- [ ] `backend/tests/test_code_generator.py` — stubs for STAGE-03
- [ ] `backend/tests/test_visual_polisher.py` — stubs for STAGE-04
- [ ] `backend/tests/test_exporter.py` — stubs for STAGE-05
- [ ] `backend/tests/test_multi_stage.py` — stubs for STAGE-06 (SSE events per stage)
- [ ] `uv add anthropic` — add Anthropic SDK dependency

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| WASM loads in browser | STAGE-05 | Requires browser runtime | Export via CLI, open in browser, verify no console errors |
| Visual polish visible in game | STAGE-04 | Aesthetic evaluation | Run pipeline, inspect generated GDScript for shader/palette refs |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
