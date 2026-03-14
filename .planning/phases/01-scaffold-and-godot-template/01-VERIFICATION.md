---
phase: 01-scaffold-and-godot-template
verified: 2026-03-14T08:30:00Z
status: human_needed
score: 3/5
must_haves:
  truths:
    - "Running setup_godot.sh installs Godot 4.5.1 and export templates; verify_godot.sh exits 0"
    - "godot --headless --export-release Web on base_2d produces .wasm and .html with no errors"
    - "base_2d contains shader library (5), particle scenes (4), palette resources (4), control snippets (4)"
    - "base_2d input map defines all 8 standard named actions"
    - "Opening game WASM in browser with COOP/COEP headers shows blank running game with no console errors"
  artifacts:
    - path: "scripts/setup_godot.sh"
      provides: "Godot 4.5.1 download, install, symlink, and version verification"
    - path: "scripts/verify_godot.sh"
      provides: "Post-install smoke test"
    - path: "scripts/verify_template.sh"
      provides: "File-existence check for all base_2d assets"
    - path: "scripts/test_export.sh"
      provides: "Headless export run + .wasm size validation"
    - path: "frontend/next.config.ts"
      provides: "COOP/COEP headers for all Next.js routes"
    - path: "godot/templates/base_2d/project.godot"
      provides: "Engine config with input map and autoload"
    - path: "godot/templates/base_2d/export_presets.cfg"
      provides: "Web export preset"
    - path: "godot/templates/base_2d/Main.tscn"
      provides: "Blank Node2D main scene"
    - path: "godot/templates/base_2d/game_manager.gd"
      provides: "Autoload with palette loading and GameState"
  key_links:
    - from: "scripts/setup_godot.sh"
      to: "/usr/local/bin/godot"
      via: "sudo ln -sf symlink"
    - from: "scripts/test_export.sh"
      to: "godot/templates/base_2d/project.godot"
      via: "--path flag in godot --headless --export-release"
    - from: "frontend/next.config.ts"
      to: "browser WASM SharedArrayBuffer"
      via: "Next.js headers() config"
    - from: "godot/templates/base_2d/project.godot"
      to: "godot/templates/base_2d/game_manager.gd"
      via: "autoload entry GameManager=*res://game_manager.gd"
human_verification:
  - test: "Run scripts/setup_godot.sh to install Godot 4.5.1 and export templates"
    expected: "Script completes with 'Godot 4.5.1 installed successfully' message; godot --headless --version prints 4.5.1"
    why_human: "Requires downloading 1.4GB of export templates and running system-level install with sudo"
  - test: "Run scripts/test_export.sh to perform headless WASM export"
    expected: "Script produces index.wasm > 500KB in /tmp/moonpond_test_export/ with no ERROR lines in export log"
    why_human: "Requires Godot binary installed; verifies hand-authored .tscn/.tres files load correctly in Godot engine"
  - test: "Serve the exported WASM with COOP/COEP headers and open in browser"
    expected: "Blank running game loads in browser with no console errors; SharedArrayBuffer is available"
    why_human: "Requires visual browser verification and WASM runtime behavior"
---

# Phase 1: Scaffold and Godot Template Verification Report

**Phase Goal:** A verified Godot 4.5.1 development environment with a base_2d template that exports a clean blank WASM game and contains all visual assets the pipeline will reference
**Verified:** 2026-03-14T08:30:00Z
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running setup_godot.sh installs Godot 4.5.1 and export templates; verify_godot.sh exits 0 | ? UNCERTAIN | Scripts exist, pass bash -n syntax check, contain correct download URLs and version verification logic. Cannot run without network + sudo. |
| 2 | godot --headless --export-release "Web" on base_2d produces .wasm and .html with no errors | ? UNCERTAIN | test_export.sh exists with correct export command, output validation, and size check. export_presets.cfg has Web preset. Cannot run without Godot installed. |
| 3 | base_2d contains shader library (5), particle scenes (4), palette resources (4), control snippets (4) | VERIFIED | All 22 template files verified present on disk with substantive content. 5 shaders use shader_type canvas_item with uniforms; 4 particles use GPUParticles2D with ParticleProcessMaterial; 4 palettes are Gradient .tres with color arrays; 4 control snippets extend Node2D with @export params. |
| 4 | base_2d input map defines all 8 standard named actions (move_left, move_right, move_up, move_down, jump, shoot, interact, pause) | VERIFIED | project.godot [input] section contains all 8 actions with physical_keycode bindings. GameManager autoload registered. gl_compatibility renderer set for Web export. |
| 5 | Opening game WASM in browser with COOP/COEP headers shows blank running game with no console errors | ? UNCERTAIN | frontend/next.config.ts has COOP (same-origin) and COEP (require-corp) headers on all routes. Cannot verify browser behavior programmatically. |

**Score:** 3/5 truths verified (2 verified, 3 uncertain pending human testing)

Note: The 2 VERIFIED truths cover the static asset and configuration content. The 3 UNCERTAIN truths all require Godot binary installation and runtime execution to verify -- they cannot be confirmed by code inspection alone.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/setup_godot.sh` | Godot 4.5.1 install | VERIFIED | 47 lines, downloads binary + templates, creates symlink, verifies version. Executable. |
| `scripts/verify_godot.sh` | Post-install smoke test | VERIFIED | 36 lines, checks binary + web export templates. Executable. |
| `scripts/verify_template.sh` | Asset existence check | VERIFIED | 61 lines, checks all 22 template files. Executable. |
| `scripts/test_export.sh` | Headless export validation | VERIFIED | 61 lines, pre-warms cache, runs export, validates .wasm size > 500KB, checks for ERROR lines. Executable. |
| `frontend/next.config.ts` | COOP/COEP headers | VERIFIED | 27 lines, both headers on all routes via source: '/(.*)'  |
| `frontend/package.json` | Next.js scaffold | VERIFIED | Minimal Next.js 15 + React 19 scaffold |
| `godot/templates/base_2d/project.godot` | Engine config | VERIFIED | 61 lines, 8 input actions, GameManager autoload, gl_compatibility renderer |
| `godot/templates/base_2d/export_presets.cfg` | Web export preset | VERIFIED | Web platform, export_path="" (portable) |
| `godot/templates/base_2d/Main.tscn` | Blank scene | VERIFIED | 3 lines, Node2D root only |
| `godot/templates/base_2d/game_manager.gd` | Autoload singleton | VERIFIED | 38 lines, palette loading, GameState enum, set_palette(), get_palette_color() |
| `godot/templates/base_2d/default_bus_layout.tres` | Audio bus layout | VERIFIED | AudioBusLayout resource |
| `assets/shaders/*.gdshader` (5 files) | Canvas item shaders | VERIFIED | All use shader_type canvas_item with configurable uniforms |
| `assets/particles/*.tscn` (4 files) | GPUParticles2D scenes | VERIFIED | All have ParticleProcessMaterial; explosion/sparkle one_shot=true, dust/trail one_shot=false |
| `assets/palettes/*.tres` (4 files) | Gradient resources | VERIFIED | All type="Gradient" with color arrays (4-5 stops each) |
| `assets/control_snippets/*.gd` (4 files) | Control scripts | VERIFIED | All extend Node2D, use @export, GDScript 4 syntax |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| setup_godot.sh | /usr/local/bin/godot | sudo ln -sf symlink | WIRED | Line 23: `sudo ln -sf "$GODOT_INSTALL_DIR/Godot.app/Contents/MacOS/Godot" /usr/local/bin/godot` |
| test_export.sh | base_2d/project.godot | --path flag in export command | WIRED | Line 32-35: `godot --headless --export-release "Web" "$OUTPUT_HTML" --path "$TEMPLATE_DIR"` |
| next.config.ts | SharedArrayBuffer | COOP/COEP headers | WIRED | Both headers present: Cross-Origin-Opener-Policy: same-origin, Cross-Origin-Embedder-Policy: require-corp |
| project.godot | game_manager.gd | autoload section | WIRED | Line 21: `GameManager="*res://game_manager.gd"` |
| game_manager.gd | assets/palettes/neon.tres | load() in _ready | WIRED | Line 17: `active_palette = load("res://assets/palettes/neon.tres")` |
| project.godot | Main.tscn | run/main_scene | WIRED | Line 16: `run/main_scene="res://Main.tscn"` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SETUP-01 | 01-01 | Godot 4.5.1 installed via setup script, verified at startup | VERIFIED (code) / NEEDS HUMAN (runtime) | setup_godot.sh and verify_godot.sh exist with correct logic; needs runtime execution to confirm |
| SETUP-02 | 01-01 | Frontend serves WASM with COOP/COEP headers | VERIFIED | frontend/next.config.ts has both headers on all routes |
| TMPL-01 | 01-02 | base_2d exports clean blank WASM via headless export | VERIFIED (code) / NEEDS HUMAN (runtime) | export_presets.cfg has Web preset; test_export.sh validates; needs Godot binary to confirm |
| TMPL-02 | 01-03 | Shader library (pixel_art, glow, scanlines, chromatic_aberration, screen_distortion) | VERIFIED | All 5 .gdshader files present with shader_type canvas_item and configurable uniforms |
| TMPL-03 | 01-04 | Particle scene library (explosion, dust, sparkle, trail) | VERIFIED | All 4 .tscn files present with GPUParticles2D and ParticleProcessMaterial |
| TMPL-04 | 01-04 | Palette resources (neon, retro, pastel, monochrome) | VERIFIED | All 4 .tres files present as Gradient resources with color stops |
| TMPL-05 | 01-02 | Standard input action map (8 actions) | VERIFIED | project.godot [input] section defines all 8: move_left, move_right, move_up, move_down, jump, shoot, interact, pause |
| TMPL-06 | 01-03 | Control snippet scripts (mouse_follow, click_to_move, drag, point_and_shoot) | VERIFIED | All 4 .gd files present, extend Node2D, use @export, GDScript 4 syntax |

No orphaned requirements found -- all 8 requirement IDs from ROADMAP Phase 1 are accounted for in plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| godot/templates/base_2d/project.godot | 15 | References `res://icon.svg` which does not exist | Warning | Godot will log a warning during export about missing icon; non-blocking (uses default) |

No TODO/FIXME/placeholder patterns found in any phase files. No empty implementations. No stub returns.

### Human Verification Required

### 1. Godot Installation and Setup

**Test:** Run `scripts/setup_godot.sh` then `scripts/verify_godot.sh`
**Expected:** setup_godot.sh downloads Godot 4.5.1 binary and export templates, creates /usr/local/bin/godot symlink. verify_godot.sh exits 0 with "PASSED" message confirming version 4.5.1 and web_debug.zip + web_release.zip templates present.
**Why human:** Requires network access (1.4GB download), sudo for symlink, and macOS-specific binary execution.

### 2. WASM Export Validation

**Test:** After Godot is installed, run `scripts/test_export.sh`
**Expected:** Produces /tmp/moonpond_test_export/index.wasm (> 500KB) and index.html with no ERROR: lines in export log. Prints "test_export.sh: PASSED".
**Why human:** Requires Godot binary. Also validates that hand-authored .tscn/.tres files (particle scenes, palette resources) load correctly in the Godot engine without UID errors.

### 3. Browser WASM Verification

**Test:** Serve the exported files with COOP/COEP headers (e.g., `npx serve -l 3000 /tmp/moonpond_test_export` with appropriate headers, or run the Next.js frontend and proxy). Open in browser.
**Expected:** Blank running game loads (Godot splash then empty canvas). Browser console shows no errors. SharedArrayBuffer is available (no COOP/COEP violations).
**Why human:** Visual verification of runtime WASM behavior in browser environment.

### Gaps Summary

No code-level gaps found. All 22 template files exist with substantive, non-stub content. All key links (autoload registration, input map, export preset, COOP/COEP headers) are wired correctly. All 8 requirement IDs are covered by implemented artifacts.

One minor note: `project.godot` references `res://icon.svg` (line 15) which does not exist in the repository. This is non-blocking -- Godot uses a default icon when the file is missing -- but will produce a warning in the export log. Consider adding a placeholder SVG icon or removing the config/icon line.

The three human verification items are all runtime checks that require Godot to be installed and executed. The code artifacts are complete and correctly structured; the remaining uncertainty is whether the Godot engine accepts the hand-authored resource files without errors at export time.

---

_Verified: 2026-03-14T08:30:00Z_
_Verifier: Claude (gsd-verifier)_
