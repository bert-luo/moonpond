---
phase: 9
slug: add-3d-game-generation-support-to-agentic-pipeline
status: active
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-20
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `cd backend && uv run pytest backend/tests/test_agentic_models.py backend/tests/test_file_generator_prompt.py backend/tests/test_agentic_pipeline.py -x -q` |
| **Full suite command** | `cd backend && uv run pytest backend/tests/ -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command above
- **After every plan wave:** Run `cd backend && uv run pytest backend/tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | Schema + spec gen | unit | `uv run pytest backend/tests/test_agentic_models.py -x -q` | YES (existing) | pending |
| 09-01-02 | 01 | 1 | base_3d template | filesystem | `test -f .../base_3d/export_presets.cfg && ...` | N/A (shell) | pending |
| 09-02-01 | 02 | 2 | File gen dynamic prompt + exporter | unit | `uv run pytest backend/tests/test_file_generator_prompt.py backend/tests/test_agentic_pipeline.py -x -q` | YES (existing) | pending |
| 09-02-02 | 02 | 2 | 3D prompt + exporter tests | unit | `uv run pytest backend/tests/test_file_generator_prompt.py -k "3d_prompt" backend/tests/test_agentic_pipeline.py -k "template_dir" -x -q` | YES (created in task) | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

All test files already exist in the project:

- [x] `backend/backend/tests/test_agentic_models.py` — test perspective field default and validation (Plan 09-01 Task 1 adds tests here)
- [x] `backend/backend/tests/test_file_generator_prompt.py` — test prompt builder outputs for 2D vs 3D (Plan 09-02 Task 2 adds 3D tests here)
- [x] `backend/backend/tests/test_agentic_pipeline.py` — test exporter template selection logic (Plan 09-02 Task 2 adds template_dir tests here)

*No new test files needed. All tests go into existing files following the project's flat test directory convention (`backend/backend/tests/test_*.py`).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 3D game renders in browser | End-to-end 3D | Requires Godot export + browser | Generate a 3D game, export WASM, verify Camera3D renders scene |
| Shader compatibility in 3D | base_3d template | Requires visual inspection | Apply glow shader to 3D scene, verify no errors |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready
