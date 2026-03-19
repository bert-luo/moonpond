---
phase: 8
slug: agentic-template-decoupling
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `cd backend && uv run pytest tests/ -x -q` |
| **Full suite command** | `cd backend && uv run pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | Template slim | unit | `cd backend && uv run pytest tests/pipelines/test_template_slim.py -v` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | Input map expansion | unit | `cd backend && uv run pytest tests/pipelines/agentic/test_input_map.py -v` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | System prompt update | unit | `cd backend && uv run pytest tests/pipelines/agentic/test_file_generator.py -v` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 2 | Pipeline integration | unit | `cd backend && uv run pytest tests/pipelines/agentic/test_agentic_pipeline.py -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/pipelines/test_template_slim.py` — verify template no longer contains game_manager.gd, Main.tscn
- [ ] `tests/pipelines/agentic/test_input_map.py` — test expand_input_map() with known keycodes
- [ ] `tests/pipelines/agentic/test_file_generator.py` — test system prompt contains skeleton, asset paths

*Existing test infrastructure covers framework and fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LLM generates valid project.godot | Autoload correctness | Requires live LLM call | Run agentic pipeline on test prompt, inspect project/project.godot for [autoload] and [input] sections |
| Other pipelines unaffected | Regression safety | Requires live pipeline run | Run contract pipeline on test prompt, verify export succeeds |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
