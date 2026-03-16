---
phase: 4
slug: frontend-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest (jsdom environment) |
| **Config file** | `frontend/vitest.config.ts` — Wave 0 creates |
| **Quick run command** | `cd frontend && npx vitest run --reporter=dot` |
| **Full suite command** | `cd frontend && npx vitest run` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx vitest run --reporter=dot`
- **After every plan wave:** Run `cd frontend && npx vitest run`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 0 | (infra) | setup | `npx vitest run` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | FE-01 | smoke (visual) | Manual verify at 1280px | N/A | ⬜ pending |
| 04-02-02 | 02 | 1 | FE-02 | unit (hook) | `vitest run hooks/useGeneration.test.ts` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 1 | FE-03 | unit (reducer) | `vitest run types/generation.test.ts` | ❌ W0 | ⬜ pending |
| 04-02-04 | 02 | 1 | FE-04 | unit (component) | `vitest run components/GameViewer.test.tsx` | ❌ W0 | ⬜ pending |
| 04-02-05 | 02 | 1 | FE-05 | unit (component) | `vitest run components/GameViewer.test.tsx` | ❌ W0 | ⬜ pending |
| 04-02-06 | 02 | 1 | FE-06 | unit (component) | `vitest run components/ChatPanel.test.tsx` | ❌ W0 | ⬜ pending |
| 04-02-07 | 02 | 1 | FE-07 | unit (reducer+component) | `vitest run types/generation.test.ts` | ❌ W0 | ⬜ pending |
| 04-02-08 | 02 | 1 | FE-08 | unit (reducer) | `vitest run types/generation.test.ts` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/vitest.config.ts` — Vitest config with jsdom environment + React plugin
- [ ] `frontend/package.json` — add vitest, @vitejs/plugin-react, @testing-library/react, @testing-library/user-event, jsdom as devDependencies
- [ ] `frontend/app/types/generation.test.ts` — reducer unit tests (FE-03, FE-07, FE-08)
- [ ] `frontend/hooks/useGeneration.test.ts` — mock fetch + EventSource (FE-02)
- [ ] `frontend/app/components/GameViewer.test.tsx` — skeleton + iframe loading (FE-04, FE-05)
- [ ] `frontend/app/components/ChatPanel.test.tsx` — controls legend (FE-06)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Two-column layout at 1280px | FE-01 | Visual/layout verification | Open app at 1280px viewport, confirm ChatPanel left + GameViewer right, both visible |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
