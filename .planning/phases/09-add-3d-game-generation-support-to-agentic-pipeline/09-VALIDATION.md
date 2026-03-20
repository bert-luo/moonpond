---
phase: 9
slug: add-3d-game-generation-support-to-agentic-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| **Quick run command** | `cd backend && uv run pytest tests/pipelines/agentic/ -x -q` |
| **Full suite command** | `cd backend && uv run pytest tests/ -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/pipelines/agentic/ -x -q`
- **After every plan wave:** Run `cd backend && uv run pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | Schema + spec gen | unit | `uv run pytest tests/pipelines/agentic/test_models.py tests/pipelines/agentic/test_spec_generator.py -x -q` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 1 | File gen dynamic prompt | unit | `uv run pytest tests/pipelines/agentic/test_file_generator.py -x -q` | ❌ W0 | ⬜ pending |
| 09-03-01 | 03 | 2 | Exporter template selection + base_3d | unit | `uv run pytest tests/pipelines/test_exporter.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/pipelines/agentic/test_models.py` — test perspective field default and validation
- [ ] `tests/pipelines/agentic/test_spec_generator.py` — test perspective in tool schema
- [ ] `tests/pipelines/agentic/test_file_generator.py` — test prompt builder outputs for 2D vs 3D
- [ ] `tests/pipelines/test_exporter.py` — test template selection logic

*Existing test infrastructure (pytest + fixtures) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 3D game renders in browser | End-to-end 3D | Requires Godot export + browser | Generate a 3D game, export WASM, verify Camera3D renders scene |
| Shader compatibility in 3D | base_3d template | Requires visual inspection | Apply glow shader to 3D scene, verify no errors |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
