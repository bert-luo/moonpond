---
phase: 1
slug: scaffold-and-godot-template
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Shell scripts (no pytest needed for Phase 1) |
| **Config file** | none — Wave 0 creates scripts |
| **Quick run command** | `bash scripts/verify_template.sh` |
| **Full suite command** | `bash scripts/verify_godot.sh && bash scripts/test_export.sh` |
| **Estimated runtime** | ~30-60 seconds (dominated by headless export) |

---

## Sampling Rate

- **After every task commit:** Run `bash scripts/verify_template.sh`
- **After every plan wave:** Run `bash scripts/verify_godot.sh && bash scripts/test_export.sh`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | SETUP-01 | smoke | `bash scripts/verify_godot.sh` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | SETUP-01 | smoke | `bash scripts/verify_godot.sh` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 0 | SETUP-02 | manual | `curl -I http://localhost:3000 \| grep -i cross-origin` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 0 | TMPL-01 | smoke | `bash scripts/test_export.sh` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 0 | TMPL-01 | smoke | `bash scripts/test_export.sh` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 1 | TMPL-02 | file check | `bash scripts/verify_template.sh` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 1 | TMPL-03 | file check | `bash scripts/verify_template.sh` | ❌ W0 | ⬜ pending |
| 1-03-03 | 03 | 1 | TMPL-04 | file check | `bash scripts/verify_template.sh` | ❌ W0 | ⬜ pending |
| 1-03-04 | 03 | 1 | TMPL-05 | grep | `grep -c "move_left\|move_right\|move_up\|move_down\|jump\|shoot\|interact\|pause" godot/templates/base_2d/project.godot` | ❌ W0 | ⬜ pending |
| 1-03-05 | 03 | 1 | TMPL-06 | file check | `bash scripts/verify_template.sh` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/setup_godot.sh` — downloads and installs Godot 4.5.1 headless + export templates
- [ ] `scripts/verify_godot.sh` — checks version string (`4.5.1`) and export template directory exists
- [ ] `scripts/verify_template.sh` — checks all required files exist in `godot/templates/base_2d/`
- [ ] `scripts/test_export.sh` — runs `godot --headless --export-release "Web"` and validates .wasm output
- [ ] `godot/templates/base_2d/` directory — base template project scaffold

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Browser shows blank running game with no console errors | TMPL-01 | Requires browser with COOP/COEP headers; can't automate headless | Serve with `npx serve -p 8080` (or dev server); open in browser; check DevTools console |
| COOP/COEP headers served correctly | SETUP-02 | Requires running Next.js dev server | `curl -I http://localhost:3000` and verify `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` present |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
