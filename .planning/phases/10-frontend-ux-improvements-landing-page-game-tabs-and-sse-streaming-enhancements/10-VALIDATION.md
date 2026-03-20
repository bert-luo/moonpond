---
phase: 10
slug: frontend-ux-improvements-landing-page-game-tabs-and-sse-streaming-enhancements
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | vitest 4.x + React Testing Library 16.x |
| **Config file** | `frontend/vitest.config.mts` |
| **Quick run command** | `cd frontend && npm test` |
| **Full suite command** | `cd frontend && npm test` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npm test`
- **After every plan wave:** Run `cd frontend && npm test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | Backend SSE events | unit | `cd backend && python -m pytest tests/ -k sse` | ✅ extend | ⬜ pending |
| 10-02-01 | 02 | 1 | AppState multi-session | unit | `cd frontend && npm test -- generation.test.ts` | ✅ extend | ⬜ pending |
| 10-02-02 | 02 | 1 | SSE dispatch with sessionId | unit | `cd frontend && npm test -- generation.test.ts` | ✅ extend | ⬜ pending |
| 10-03-01 | 03 | 2 | LandingPage renders when 0 games | unit | `cd frontend && npm test -- LandingPage.test.tsx` | ❌ W0 | ⬜ pending |
| 10-03-02 | 03 | 2 | LandingPage hides on generation | unit | `cd frontend && npm test -- LandingPage.test.tsx` | ❌ W0 | ⬜ pending |
| 10-04-01 | 04 | 2 | GameTabs renders titles | unit | `cd frontend && npm test -- GameTabs.test.tsx` | ❌ W0 | ⬜ pending |
| 10-04-02 | 04 | 2 | GameTabs plus button creates session | unit | `cd frontend && npm test -- GameTabs.test.tsx` | ❌ W0 | ⬜ pending |
| 10-04-03 | 04 | 2 | GameTabs select switches game panel | unit | `cd frontend && npm test -- GameTabs.test.tsx` | ❌ W0 | ⬜ pending |
| 10-05-01 | 05 | 2 | ChatPanel spec_info message | unit | `cd frontend && npm test -- ChatPanel.test.tsx` | ✅ extend | ⬜ pending |
| 10-05-02 | 05 | 2 | ChatPanel file_written message | unit | `cd frontend && npm test -- ChatPanel.test.tsx` | ✅ extend | ⬜ pending |
| 10-05-03 | 05 | 2 | ChatPanel controls message | unit | `cd frontend && npm test -- ChatPanel.test.tsx` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/__tests__/GameTabs.test.tsx` — stubs for GameTabs rendering and interaction
- [ ] `frontend/__tests__/LandingPage.test.tsx` — stubs for landing page show/hide conditions

*Existing infrastructure covers backend and state management tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Moon/water background visual quality | Landing page design | CSS visual — no automated assertion | Load app with 0 games, verify background renders correctly |
| Tab switching updates game panel iframe | Multi-game sessions | Iframe content swap | Create 2 games, switch tabs, verify correct game displays |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
