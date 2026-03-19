---
phase: 6
slug: programmatic-tscn-generation-and-display-configuration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | backend/pyproject.toml |
| **Quick run command** | `cd backend && uv run pytest backend/tests/ -x -q` |
| **Full suite command** | `cd backend && uv run pytest backend/tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest backend/tests/ -x -q`
- **After every plan wave:** Run `cd backend && uv run pytest backend/tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | TscnBuilder serialization | unit | `uv run pytest backend/tests/test_tscn_builder.py -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | @onready parser | unit | `uv run pytest backend/tests/test_onready_parser.py -q` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 2 | SceneAssembler Main.tscn | unit | `uv run pytest backend/tests/test_scene_assembler.py -q` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | SceneAssembler sub-scenes | unit | `uv run pytest backend/tests/test_scene_assembler.py -q` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 3 | Pipeline integration | integration | `uv run pytest backend/tests/test_contract_pipeline.py -q` | ✅ | ⬜ pending |
| 06-03-02 | 03 | 3 | Display settings | unit | `uv run pytest backend/tests/ -k viewport -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_tscn_builder.py` — TscnBuilder serialization tests
- [ ] `backend/tests/test_onready_parser.py` — @onready regex parser tests
- [ ] `backend/tests/test_scene_assembler.py` — SceneAssembler integration tests

*Existing infrastructure covers test framework setup.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Generated .tscn loads in Godot | Full integration | Requires Godot binary | Export a test game and verify no load errors |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
