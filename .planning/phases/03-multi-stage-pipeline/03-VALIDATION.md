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
| 03-01-01 | 01 | 1 | STAGE-01, STAGE-06 | import | `cd backend && uv run python -c "from backend.stages.models import GameSpec, GameDesign; print('OK')"` | n/a (import check) | ⬜ pending |
| 03-01-02 | 01 | 1 | STAGE-02 | import | `cd backend && uv run python -c "from backend.stages.prompt_enhancer import run_prompt_enhancer; from backend.stages.game_designer import run_game_designer; print('OK')"` | n/a (import check) | ⬜ pending |
| 03-02-01 | 02 | 2 | STAGE-03 | import | `cd backend && uv run python -c "from backend.stages.code_generator import run_code_generator; print('OK')"` | n/a (import check) | ⬜ pending |
| 03-02-02 | 02 | 2 | STAGE-04, STAGE-05 | import | `cd backend && uv run python -c "from backend.stages.visual_polisher import run_visual_polisher; from backend.stages.exporter import run_exporter; print('OK')"` | n/a (import check) | ⬜ pending |
| 03-03-01 | 03 | 3 | STAGE-01 to STAGE-06 | unit | `cd backend && uv run pytest backend/backend/tests/test_stages.py -v` | ❌ W3 | ⬜ pending |
| 03-03-02 | 03 | 3 | STAGE-06 | integration | `cd backend && uv run pytest backend/backend/tests/test_multi_stage_pipeline.py -v` | ❌ W3 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Wave 1 and Wave 2 tasks use import-only verification (no test files needed). Test files are created in Wave 3 (Plan 03-03).

- [ ] `uv add anthropic` — add Anthropic SDK dependency (Plan 03-01, Task 1)

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
