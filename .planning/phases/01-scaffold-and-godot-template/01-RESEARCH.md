# Phase 1: Scaffold and Godot Template - Research

**Researched:** 2026-03-13
**Domain:** Godot 4.5.1 headless WASM export, project scaffold, GDScript template assets
**Confidence:** MEDIUM-HIGH (Godot 4.5.1 release confirmed; macOS export template path is MEDIUM confidence — verify by running setup script and checking directory; core patterns are HIGH)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SETUP-01 | Godot 4.5.1 headless binary and export templates installed via setup script, version verified at startup | Confirmed: exact filenames, download URLs, macOS export template path, version flag documented below |
| SETUP-02 | Dev server serves WASM files with correct COOP/COEP headers | Confirmed: Next.js headers() config pattern documented; both headers required for SharedArrayBuffer |
| TMPL-01 | base_2d template exports clean blank WASM with no errors via headless export | Confirmed: export_presets.cfg structure, CLI flags, output file list, validation approach documented |
| TMPL-02 | base_2d includes shader library (pixel_art, glow, scanlines, chromatic_aberration, screen_distortion) | Confirmed: .gdshader file format, canvas_item shader_type, godotshaders.com as reference source |
| TMPL-03 | base_2d includes particle scene library (explosion, dust, sparkle, trail) | Confirmed: GPUParticles2D .tscn scenes, one_shot flag for burst effects, key parameters |
| TMPL-04 | base_2d includes curated color palette resources (neon, retro, pastel, monochrome as Gradient .tres files) | Confirmed: Gradient resource saves as .tres; Godot 4.4+ has ColorPalette class but Gradient is simpler |
| TMPL-05 | base_2d pre-defines standard input action map (8 named actions) | Confirmed: project.godot [input] section format, InputEventKey physical_keycode values, exact syntax |
| TMPL-06 | base_2d includes control snippet scripts (mouse_follow, click_to_move, drag, point_and_shoot) | Confirmed: GDScript 4.x syntax patterns for each control type documented |
</phase_requirements>

---

## Summary

Phase 1 establishes the single most critical artifact in the Moonpond pipeline: a Godot 4.5.1 project template that exports a clean WASM bundle and contains all visual assets the LLM pipeline will reference by name. Everything in Phases 2-4 builds on top of what gets committed here.

Godot 4.5.1-stable was released October 15, 2024. The confirmed download filenames are `Godot_v4.5.1-stable_macos.universal.zip` (Universal 2 binary supporting both ARM64 Apple Silicon and Intel x86_64) and `Godot_v4.5.1-stable_export_templates.tpz` (1.4 GB). On macOS, the binary runs via `Godot.app/Contents/MacOS/Godot --headless`. Export templates install to `~/Library/Application Support/Godot/export_templates/4.5.1.stable/`.

The base_2d template must be minimal — export presets, input map, audio bus layout, shader resources, palette resources, particle scenes, and control snippet scripts — but NO gameplay nodes in the main scene. The LLM generates the scene tree from scratch. A template that includes gameplay structure over-constrains the LLM across diverse game genres (platformer vs. top-down vs. puzzle vs. runner). The input map defines eight named actions that the Code Generator stage MUST reference exactly.

**Primary recommendation:** Write a `scripts/setup_godot.sh` that downloads, extracts, installs, and verifies the exact 4.5.1 binary + templates. Use `Godot.app/Contents/MacOS/Godot --version` output to assert the version string before any project work. Commit `export_presets.cfg` to the template — never generate it with the LLM.

---

## Standard Stack

### Core

| Technology | Version | Purpose | Why Standard |
|------------|---------|---------|--------------|
| Godot 4.5.1-stable | 4.5.1.stable | Game engine + headless WASM exporter | Exact version locked by project; export_presets.cfg is version-specific; different patch versions silently break exports |
| GDScript 4.x | Bundled with Godot 4.5.1 | Game logic scripting language | Native to Godot 4; no external dependency |
| `.gdshader` files | Godot shading language | 2D canvas_item shaders (pixel_art, glow, scanlines, etc.) | Godot's built-in shader format; assigned to CanvasItem materials |
| `GPUParticles2D` scenes (.tscn) | Godot 4 | Particle effect scenes | GPU-accelerated; used for explosion, dust, sparkle, trail |
| `Gradient` resource (.tres) | Godot 4 | Color palette resources | Built-in Godot resource; saves/loads as .tres; inspectable in editor |

### Supporting

| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| curl / wget | System | Download Godot binary + templates | Setup script only |
| unzip | System | Extract .zip and .tpz archives | Setup script only; .tpz is a renamed .zip |
| Next.js headers() | In next.config.js | COOP/COEP headers for WASM serving | Needed from Phase 4 onward; scaffold now so it's not missed |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GPUParticles2D | CPUParticles2D | CPU particles don't need GPU; more compatible but lower performance; GPUParticles2D is preferred in Godot 4 for visual quality |
| Gradient .tres | ColorPalette class (Godot 4.4+) | ColorPalette is newer and more purpose-built but Gradient is simpler and more widely documented; stick with Gradient for v1 |
| macOS universal binary | Linux x86_64 binary | Linux binary is required for CI/server; macOS binary is needed for local dev on this machine (macOS); plan to support both in setup script |

---

## Architecture Patterns

### Recommended Project Structure

```
moonpond/
  scripts/
    setup_godot.sh          # Downloads, installs, verifies Godot 4.5.1 + templates
  godot/
    templates/
      base_2d/              # Committed Godot project — never modified in place
        project.godot       # Engine config: input map, audio bus, app name
        export_presets.cfg  # Web preset — committed, never LLM-generated
        default_bus_layout.tres  # Audio bus layout
        Main.tscn           # Blank main scene — no gameplay nodes
        game_manager.gd     # Thin autoload: job_id, game_state, palette reference
        assets/
          shaders/
            pixel_art.gdshader
            glow.gdshader
            scanlines.gdshader
            chromatic_aberration.gdshader
            screen_distortion.gdshader
          particles/
            explosion.tscn
            dust.tscn
            sparkle.tscn
            trail.tscn
          palettes/
            neon.tres
            retro.tres
            pastel.tres
            monochrome.tres
          control_snippets/
            mouse_follow.gd
            click_to_move.gd
            drag.gd
            point_and_shoot.gd
  frontend/                 # Scaffolded Next.js app (Phase 4 content)
    next.config.ts          # COOP/COEP headers — set up now, used in Phase 4
  backend/                  # FastAPI backend (Phase 2 content)
  games/                    # gitignored; per-job runtime output
```

### Pattern 1: Minimal Template Contract

**What:** The base_2d template provides infrastructure only — no gameplay nodes in the main scene. The LLM generates the full scene tree for each game. The template's "contract" is documented in the system prompt for the Code Generator stage: which resource paths always exist, which input action names are pre-defined, which autoloads are present.

**When to use:** Always. A template that includes a Player node or Camera2D hard-wires assumptions that break for top-down shooters, puzzle games, card games, etc.

**What to include in the template:**
- `project.godot` with input map, app name, audio bus, autoloads
- `export_presets.cfg` with the "Web" preset fully configured
- `assets/shaders/` — .gdshader files referenced by name
- `assets/particles/` — .tscn scenes instantiated by generated code
- `assets/palettes/` — .tres Gradient resources loaded by game_manager.gd
- `assets/control_snippets/` — .gd scripts sourced by generated player controllers
- A blank `Main.tscn` with only a Node2D root — no children

**What NOT to include:**
- CharacterBody2D, RigidBody2D, or any gameplay physics body
- Camera2D (genre-dependent positioning)
- Any AnimationPlayer, Timer, or game-logic nodes

### Pattern 2: Committed export_presets.cfg

**What:** The `export_presets.cfg` file is authored once by hand (or via the Godot editor), committed to the template, and never touched by the LLM or the pipeline. It contains the exact "Web" export preset configuration for Godot 4.5.1.

**Why critical:** `export_presets.cfg` references the binary export template path, feature flags, and texture compression settings. Even a minor deviation causes silent export failure. LLMs hallucinate wrong settings.

**Minimal Web preset structure:**
```ini
[preset.0]

name="Web"
platform="Web"
runnable=true
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path=""
encryption_include_filters=""
encryption_exclude_filters=""
script_export_mode=1

[preset.0.options]

custom_template/debug=""
custom_template/release=""
variant/extensions_support=false
vram_texture_compression/for_mobile=false
html/export_icon=true
html/custom_html_shell=""
html/head_include=""
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
html/experimental_virtual_keyboard=false
progressive_web_app/enabled=false
```

**Note:** The `export_path` field must be set to the output HTML path before each export run, OR specified on the CLI. Setting it to empty and specifying on CLI is the cleaner approach.

### Pattern 3: project.godot Input Map Format

**What:** Input actions are defined in the `[input]` section of `project.godot`. Each action maps to one or more `InputEventKey` objects with `physical_keycode` values (hardware-independent).

**Example for the eight standard actions:**
```ini
[input]

move_left={
"deadzone": 0.5,
"events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":4194319,"key_label":0,"unicode":0,"echo":false,"script":null)]
}
move_right={
"deadzone": 0.5,
"events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":4194321,"key_label":0,"unicode":0,"echo":false,"script":null)]
}
```

**Physical keycodes for the 8 standard actions:**

| Action | Primary Key | physical_keycode |
|--------|-------------|-----------------|
| move_left | Left arrow | 4194319 |
| move_right | Right arrow | 4194321 |
| move_up | Up arrow | 4194320 |
| move_down | Down arrow | 4194322 |
| jump | Space | 32 |
| shoot | Z | 90 |
| interact | E | 69 |
| pause | Escape | 4194305 |

**Note:** These physical_keycode values are derived from training knowledge. The easiest approach is to define the actions using the Godot editor UI (Project > Project Settings > Input Map) and then read the resulting `project.godot` for the exact values. The editor writes the correct format.

### Pattern 4: .gdshader File Structure

**What:** All five shader files use `shader_type canvas_item;` (for 2D sprites and CanvasItem nodes). Each shader exposes uniforms so the LLM can configure them at runtime via GDScript.

**Template for pixel_art.gdshader:**
```glsl
shader_type canvas_item;

uniform float pixel_size: hint_range(1.0, 64.0) = 4.0;
uniform sampler2D palette_texture: hint_default_white;
uniform bool use_palette = false;

void fragment() {
    vec2 uv = floor(UV / pixel_size) * pixel_size;
    vec4 color = texture(TEXTURE, uv);
    COLOR = color;
}
```

**Template for glow.gdshader:**
```glsl
shader_type canvas_item;

uniform float glow_strength: hint_range(0.0, 10.0) = 2.0;
uniform vec4 glow_color: source_color = vec4(1.0, 0.8, 0.2, 1.0);
uniform float glow_radius: hint_range(0.0, 20.0) = 3.0;

void fragment() {
    vec4 base_color = texture(TEXTURE, UV);
    float glow = 0.0;
    vec2 pixel = TEXTURE_PIXEL_SIZE;
    for (float x = -glow_radius; x <= glow_radius; x += 1.0) {
        for (float y = -glow_radius; y <= glow_radius; y += 1.0) {
            glow += texture(TEXTURE, UV + vec2(x, y) * pixel).a;
        }
    }
    glow /= (glow_radius * 2.0 + 1.0) * (glow_radius * 2.0 + 1.0);
    COLOR = mix(base_color, glow_color * glow_strength, glow * (1.0 - base_color.a));
    COLOR.a = base_color.a;
}
```

**Note:** These are simplified reference implementations. The actual .gdshader files committed to the template should be sourced from godotshaders.com (canvas_item category) for well-tested versions. The key requirement is that they compile and produce the named visual effect in Godot 4.5.1.

### Pattern 5: GPUParticles2D Scene (.tscn)

**What:** Each particle effect is a standalone .tscn file with a GPUParticles2D root node, pre-configured for the named effect. Games instantiate them with `preload("res://assets/particles/explosion.tscn").instantiate()`.

**explosion.tscn structure:**
- Root: GPUParticles2D
  - `amount`: 32
  - `lifetime`: 0.8
  - `one_shot`: true
  - `explosiveness`: 0.9
  - `process_material`: ParticleProcessMaterial (sub-resource)
    - `direction`: Vector3(0, -1, 0)
    - `spread`: 180.0
    - `initial_velocity_min`: 100.0, `initial_velocity_max`: 300.0
    - `gravity`: Vector3(0, 98, 0)
    - `scale_min`: 4.0, `scale_max`: 12.0
    - `color`: gradient from bright yellow-orange to transparent red

**dust.tscn:** continuous emission, low velocity, upward drift, semi-transparent gray
**sparkle.tscn:** one_shot, small fast particles, high explosiveness, white/yellow colors
**trail.tscn:** continuous emission, few particles, long lifetime, follows parent position

**Note:** Create these using the Godot editor rather than hand-authoring .tscn text files. The binary sub-resource UIDs in .tscn files are editor-generated; hand-writing them risks invalid resource references.

### Pattern 6: Gradient .tres Palette Resource

**What:** Each palette is a `Gradient` resource saved as a .tres file. The Gradient stores an array of colors with offset positions (0.0 to 1.0). GDScript accesses the palette via `load("res://assets/palettes/neon.tres")` and samples colors with `gradient.sample(t)`.

**neon.tres palette (4 colors):**
- 0.0: `#ff00ff` (magenta)
- 0.33: `#00ffff` (cyan)
- 0.66: `#ffff00` (yellow)
- 1.0: `#ff0040` (hot pink)

**retro.tres palette:** warm reds, oranges, tans — classic arcade feel
**pastel.tres palette:** soft pink, lavender, mint, peach
**monochrome.tres palette:** white through gray to black

**Creation approach:** Use the Godot editor to create Gradient resources visually (Inspect > New Gradient > set colors > save as .tres). Do not hand-author .tres files.

### Anti-Patterns to Avoid

- **LLM-generated export_presets.cfg:** The LLM does not know the exact binary template paths or version-specific flags. Always commit a hand-authored preset.
- **Gameplay nodes in Main.tscn:** Adding CharacterBody2D, Camera2D, or any game-logic nodes to the template over-constrains the LLM. Keep Main.tscn as a blank Node2D with only the autoload manager.
- **Hand-authoring .tscn particle scenes:** The UIDs and sub-resource format in .tscn files are fragile to hand-write. Always create them in the Godot editor.
- **Using `export_path` in export_presets.cfg:** Setting the export path in the preset hard-codes an output path that breaks when the project is copied to `games/{job_id}/project/`. Leave `export_path=""` and pass the output path on the CLI.

---

## Godot 4.5.1 Setup: Verified Facts

### Download Filenames (CONFIRMED from SourceForge mirror)

| Artifact | Filename | Size | SHA1 |
|----------|----------|------|------|
| macOS Universal binary | `Godot_v4.5.1-stable_macos.universal.zip` | 69.6 MB | 22bbffab391fc920fcdd92f65bee5f4cc661bdcc |
| Export templates | `Godot_v4.5.1-stable_export_templates.tpz` | 1.4 GB | 3a1d4d0bfaf87c6f567183a5876a3562d4e7975e |
| Linux x86_64 binary | `Godot_v4.5.1-stable_linux.x86_64.zip` | — | — |

**GitHub releases base URL:** `https://github.com/godotengine/godot/releases/download/4.5.1-stable/`

**Download URLs:**
```
https://github.com/godotengine/godot/releases/download/4.5.1-stable/Godot_v4.5.1-stable_macos.universal.zip
https://github.com/godotengine/godot/releases/download/4.5.1-stable/Godot_v4.5.1-stable_export_templates.tpz
```

### macOS Installation Path

The Godot .app bundle unpacks to `Godot.app/`. The CLI binary lives at:
```
Godot.app/Contents/MacOS/Godot
```

Symlink to invoke as `godot` from PATH:
```bash
sudo ln -sf "$(pwd)/Godot.app/Contents/MacOS/Godot" /usr/local/bin/godot
```

### Export Templates Installation Path

**macOS:** `~/Library/Application Support/Godot/export_templates/4.5.1.stable/`

**Linux:** `~/.local/share/godot/export_templates/4.5.1.stable/`

**IMPORTANT:** The directory name must be exactly `4.5.1.stable` (with a dot before "stable", not a hyphen). Using `4.5.1-stable` causes "Export template not found" with no other error.

The `.tpz` file is a renamed `.zip`. Unzip it and move the contents:
```bash
# macOS
TEMPLATES_DIR="$HOME/Library/Application Support/Godot/export_templates/4.5.1.stable"
mkdir -p "$TEMPLATES_DIR"
# tpz is a zip archive
cp Godot_v4.5.1-stable_export_templates.tpz /tmp/godot_templates.zip
unzip -o /tmp/godot_templates.zip -d /tmp/godot_templates_extracted/
mv /tmp/godot_templates_extracted/templates/* "$TEMPLATES_DIR/"
```

### Version Verification

```bash
# Verify installed binary version
godot --headless --version
# Expected output: 4.5.1.stable.official.f62fdbd (or similar hash suffix)
# Assert the first 5 chars match "4.5.1"
```

### Headless Export Command

```bash
# Export the base_2d template to verify it works
godot --headless --export-release "Web" /path/to/output/index.html --path /path/to/base_2d/
```

- `--headless` — no display required; mandatory for server/subprocess use
- `--export-release "Web"` — uses the export preset named "Web" in export_presets.cfg
- `/path/to/output/index.html` — output file path; Godot generates `.html`, `.wasm`, `.js`, `.pck` alongside it
- `--path` — path to the directory containing `project.godot`

**Output files generated:**
- `index.html` — entry point
- `index.wasm` — WebAssembly binary
- `index.js` — engine loader
- `index.pck` — packed game assets
- `index.png` — boot splash (optional)

### Exit Code Behavior

**As of Godot 4.3+:** The fix for issue #83042 (merged PR #89234, milestone 4.3) means Godot now properly returns a non-zero exit code on export failure. This means `$?` is reliable as a failure indicator starting from Godot 4.3. For safety, ALWAYS validate output file existence and size in addition to exit code — belt and suspenders.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Shader files | Custom GLSL from scratch | Source from godotshaders.com canvas_item library | Well-tested, Godot 4 compatible, covers the required effects |
| Particle effects | Hand-authored .tscn text | Create in Godot editor, commit the result | .tscn UIDs are editor-generated; hand-authored files produce invalid resource references |
| Color palettes | Code-driven color constants | Gradient .tres resources | Editor-editable, loadable as resources, samplable in GDScript |
| Input action keycodes | Hardcoded keycode integers | Define via Godot editor Project Settings > Input Map | Editor writes correct physical_keycode values; hand-authored values are error-prone |
| export_presets.cfg | LLM-generated or programmatically generated | Author once in Godot editor, commit | Version-specific binary template paths; any deviation silently breaks export |
| COOP/COEP headers | Custom middleware | Next.js headers() in next.config.ts | Standard Next.js pattern; two-line config; no custom code needed |

**Key insight:** The template must be created using the Godot editor for any artifact that contains editor-generated data (UIDs, resource paths, keycodes). Use the editor as a code-generation tool, then commit the result. The only exception is shader files, which can be hand-authored as plain text.

---

## Common Pitfalls

### Pitfall 1: Export Template Version Directory Name
**What goes wrong:** `~/.local/share/godot/export_templates/4.5.1-stable/` causes "Export template not found" — Godot expects `4.5.1.stable` (dot-separated, not hyphen before "stable").
**How to avoid:** Use `4.5.1.stable` exactly. Assert this in the setup script.

### Pitfall 2: macOS App Bundle Not Bypassing Gatekeeper
**What goes wrong:** macOS quarantines the downloaded Godot.app. `godot --headless` fails with "cannot be opened because the developer cannot be verified."
**How to avoid:**
```bash
xattr -dr com.apple.quarantine Godot.app
```
Run this immediately after unzipping the macOS binary. Include in setup script.

### Pitfall 3: WASM Requires COOP/COEP Headers
**What goes wrong:** Browser shows blank screen or "SharedArrayBuffer is not defined." The game works from `file://` but not inside the Next.js app.
**How to avoid:** Set in `next.config.ts`:
```typescript
async headers() {
  return [
    {
      source: '/(.*)',
      headers: [
        { key: 'Cross-Origin-Opener-Policy', value: 'same-origin' },
        { key: 'Cross-Origin-Embedder-Policy', value: 'require-corp' },
      ],
    },
  ]
}
```
Note: Setting COOP/COEP globally breaks any third-party iframes or scripts (e.g., OAuth popups, analytics) that load cross-origin resources. For Phase 1, this is fine — the app is local-only. Flag for Phase 4 if any cross-origin content is added.

### Pitfall 4: Template Has Gameplay Nodes — LLM Cannot Override
**What goes wrong:** A template with a Player scene or CharacterBody2D works for platformers but breaks for top-down games (wrong physics body, wrong input axes).
**How to avoid:** Keep `Main.tscn` as a blank Node2D. The LLM generates the entire scene tree for each game. Document the template contract in the Code Generator system prompt (Phase 3).

### Pitfall 5: export_presets.cfg Has Absolute export_path
**What goes wrong:** The template export_presets.cfg has `export_path="/absolute/path/to/output.html"`. When the Exporter stage copies the template to `games/{job_id}/project/`, the output path points to the wrong location.
**How to avoid:** Keep `export_path=""` in the committed preset. Always pass the output path as the CLI argument to `godot --export-release`.

### Pitfall 6: Setup Script Downloads to Wrong Directory
**What goes wrong:** Setup script runs from a different working directory; relative paths in the script point to wrong locations.
**How to avoid:** Use absolute paths throughout the setup script. Pin `SCRIPT_DIR` to the script's own location:
```bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
```

### Pitfall 7: .tpz Extraction Fails Because unzip Not Available
**What goes wrong:** macOS ships with `unzip` but some minimal environments don't have it. Also, `unzip` output structure for the templates TPZ has a `templates/` subdirectory — scripts that don't account for this end up installing to `templates/templates/`.
**How to avoid:** Use `unzip -l` to inspect the TPZ contents first. The structure is:
```
templates/
  web_debug.zip
  web_release.zip
  [platform-specific files]
```
Move `templates/*` to the final destination, not `templates/` itself.

---

## Code Examples

### Setup Script Pattern

```bash
#!/usr/bin/env bash
# scripts/setup_godot.sh
# Source: Based on confirmed Godot 4.5.1 release artifacts + community CI patterns

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GODOT_VERSION="4.5.1"
GODOT_VERSION_TAG="${GODOT_VERSION}-stable"
GODOT_INSTALL_DIR="${SCRIPT_DIR}/../godot/bin"

# macOS paths
GODOT_MACOS_ZIP="Godot_v${GODOT_VERSION_TAG}_macos.universal.zip"
GODOT_TEMPLATES_TPZ="Godot_v${GODOT_VERSION_TAG}_export_templates.tpz"
TEMPLATES_DIR="$HOME/Library/Application Support/Godot/export_templates/${GODOT_VERSION}.stable"
BASE_URL="https://github.com/godotengine/godot/releases/download/${GODOT_VERSION_TAG}"

mkdir -p "$GODOT_INSTALL_DIR"

# Download binary
curl -L -o "/tmp/${GODOT_MACOS_ZIP}" "${BASE_URL}/${GODOT_MACOS_ZIP}"
unzip -o "/tmp/${GODOT_MACOS_ZIP}" -d "$GODOT_INSTALL_DIR"

# Remove macOS quarantine flag
xattr -dr com.apple.quarantine "$GODOT_INSTALL_DIR/Godot.app" 2>/dev/null || true

# Create symlink
sudo ln -sf "$GODOT_INSTALL_DIR/Godot.app/Contents/MacOS/Godot" /usr/local/bin/godot

# Download and install export templates
curl -L -o "/tmp/${GODOT_TEMPLATES_TPZ}" "${BASE_URL}/${GODOT_TEMPLATES_TPZ}"
mkdir -p "$TEMPLATES_DIR"
cp "/tmp/${GODOT_TEMPLATES_TPZ}" /tmp/godot_templates.zip
unzip -o /tmp/godot_templates.zip -d /tmp/godot_templates_extracted/
mv /tmp/godot_templates_extracted/templates/* "$TEMPLATES_DIR/"

# Verify
INSTALLED_VERSION=$(godot --headless --version 2>/dev/null || echo "FAILED")
if [[ "$INSTALLED_VERSION" != "${GODOT_VERSION}"* ]]; then
  echo "ERROR: Expected version ${GODOT_VERSION}, got: $INSTALLED_VERSION"
  exit 1
fi
echo "Godot ${INSTALLED_VERSION} installed successfully"
```

### Headless Export Verification

```bash
# Source: Confirmed from Godot 4 CLI documentation + community CI examples

# Create output directory
mkdir -p /tmp/test_export

# Export base_2d template
godot --headless \
  --export-release "Web" \
  /tmp/test_export/index.html \
  --path "$SCRIPT_DIR/../godot/templates/base_2d"

# Validate output (never trust exit code alone — validate file existence)
WASM_FILE="/tmp/test_export/index.wasm"
if [[ ! -f "$WASM_FILE" ]]; then
  echo "ERROR: Export failed — no .wasm file produced"
  exit 1
fi
WASM_SIZE=$(stat -f%z "$WASM_FILE" 2>/dev/null || stat -c%s "$WASM_FILE")
if [[ "$WASM_SIZE" -lt 500000 ]]; then
  echo "ERROR: Export produced suspiciously small .wasm (${WASM_SIZE} bytes)"
  exit 1
fi
echo "Export OK: ${WASM_SIZE} bytes"
```

### Next.js COOP/COEP Header Config

```typescript
// next.config.ts
// Source: Next.js headers() documentation + MDN SharedArrayBuffer requirements

import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        // Apply COOP/COEP to all routes — required for Godot WASM SharedArrayBuffer
        source: '/(.*)',
        headers: [
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          {
            key: 'Cross-Origin-Embedder-Policy',
            value: 'require-corp',
          },
        ],
      },
    ]
  },
}

export default nextConfig
```

### game_manager.gd Autoload Script

```gdscript
# game_manager.gd
# Source: Godot 4 GDScript documentation + training knowledge
# Autoloaded as GameManager — available globally to all scenes

extends Node

# Active color palette — set by the pipeline's Visual Polisher stage reference
var active_palette: Gradient = null

# Game state for simple win/fail tracking
enum GameState { PLAYING, WON, LOST }
var state: GameState = GameState.PLAYING

func _ready() -> void:
    # Default palette: neon
    active_palette = load("res://assets/palettes/neon.tres")

func set_palette(palette_name: String) -> void:
    var path := "res://assets/palettes/%s.tres" % palette_name
    if ResourceLoader.exists(path):
        active_palette = load(path)

func get_palette_color(t: float) -> Color:
    if active_palette:
        return active_palette.sample(t)
    return Color.WHITE
```

### Control Snippet: mouse_follow.gd

```gdscript
# mouse_follow.gd — attach to any Node2D to make it follow the mouse
# Usage: add_child(preload("res://assets/control_snippets/mouse_follow.gd").new())
# OR: inherit from this script

extends Node2D

@export var follow_speed: float = 0.1  # 0.0 = instant, 1.0 = no movement

func _process(delta: float) -> void:
    var target := get_global_mouse_position()
    global_position = global_position.lerp(target, 1.0 - pow(follow_speed, delta))
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate Godot "headless" binary download | Standard binary runs with `--headless` flag | Godot 4.0+ | No separate binary needed; single download works for both editor and headless |
| `--export` flag (Godot 3) | `--export-release` flag (Godot 4) | Godot 4.0 | The old flag name still exists as an alias but `--export-release` is explicit and preferred |
| Exit code 0 on all export outcomes | Non-zero exit code on export failure | Godot 4.3 (PR #89234) | Can now use `$?` as a primary failure check, but still validate file existence as belt-and-suspenders |
| `HTML5` platform name in export presets | `Web` platform name | Godot 4.0+ | The preset platform must be `"Web"` not `"HTML5"` in Godot 4 |
| Godot 3 `yield()` | Godot 4 `await` | Godot 4.0 | This affects control snippet scripts; all GDScript in the template must use Godot 4 syntax |

**Deprecated/outdated:**
- `KinematicBody2D`: Replaced by `CharacterBody2D` in Godot 4
- `setget`: Replaced by `@export` and property setters in GDScript 4
- `onready`: Replaced by `@onready` decorator in GDScript 4
- String-form signal `connect("signal_name", target, "method_name")`: Replaced by `signal.connect(callable)` in Godot 4

---

## Open Questions

1. **macOS export template path: `~/Library/Application Support/Godot/` vs `~/.local/share/godot/`**
   - What we know: Linux uses `~/.local/share/godot/export_templates/`. macOS traditionally uses `~/Library/Application Support/`.
   - What's unclear: Whether Godot on macOS follows the macOS convention or the XDG convention.
   - Recommendation: The setup script should install to both locations to be safe, OR run `godot --headless --version` first and check which path it reports when templates are missing. The path Godot reports in its error message is definitive.

2. **Godot --headless .godot folder requirement on first run**
   - What we know: Issue #95287 (Godot 4.3 RC2) documented that headless export freezes without a `.godot` folder. This was filed against 4.3 RC2.
   - What's unclear: Whether this bug persisted to 4.5.1.stable.
   - Recommendation: The setup script and Exporter stage should always run `godot --headless --editor --quit --path <project>` before export to ensure the `.godot` import cache is built. This is the established CI workaround.

3. **WASM MIME type for static file serving**
   - What we know: Browsers require `.wasm` served as `application/wasm`. FastAPI's `StaticFiles` mount may serve it as `application/octet-stream`.
   - What's unclear: Whether FastAPI 0.135's StaticFiles auto-detects the WASM MIME type or requires manual override.
   - Recommendation: In Phase 2, test by loading the WASM in a browser after FastAPI serves it and check browser console for MIME type errors. Add a custom media_types dict to StaticFiles if needed.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (backend); shell assertions (setup script) |
| Config file | `backend/pytest.ini` — Wave 0 gap |
| Quick run command | `pytest backend/tests/ -x -q` |
| Full suite command | `pytest backend/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SETUP-01 | `godot --headless --version` outputs "4.5.1" prefix | smoke | `bash scripts/verify_godot.sh` | ❌ Wave 0 |
| SETUP-01 | Export templates directory exists and contains web_debug.zip | smoke | `bash scripts/verify_godot.sh` | ❌ Wave 0 |
| SETUP-02 | Next.js dev server returns COOP/COEP headers on all routes | integration | `curl -I http://localhost:3000 | grep -i cross-origin` | ❌ Wave 0 (manual) |
| TMPL-01 | Headless export produces .wasm file > 500KB | smoke | `bash scripts/test_export.sh` | ❌ Wave 0 |
| TMPL-01 | Headless export exits 0 with no ERROR: lines in stderr | smoke | `bash scripts/test_export.sh` | ❌ Wave 0 |
| TMPL-02 | All 5 shader files exist at expected paths | file check | `bash scripts/verify_template.sh` | ❌ Wave 0 |
| TMPL-03 | All 4 particle .tscn files exist | file check | `bash scripts/verify_template.sh` | ❌ Wave 0 |
| TMPL-04 | All 4 palette .tres files exist | file check | `bash scripts/verify_template.sh` | ❌ Wave 0 |
| TMPL-05 | project.godot contains all 8 input actions | grep | `grep -c "move_left\|move_right\|move_up\|move_down\|jump\|shoot\|interact\|pause" godot/templates/base_2d/project.godot` | ❌ Wave 0 |
| TMPL-06 | All 4 control snippet .gd files exist | file check | `bash scripts/verify_template.sh` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `bash scripts/verify_template.sh` (file existence check, < 1s)
- **Per wave merge:** `bash scripts/test_export.sh` (full headless export, ~30-60s)
- **Phase gate:** Full headless export + browser WASM load test before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `scripts/setup_godot.sh` — installs Godot 4.5.1 + templates
- [ ] `scripts/verify_godot.sh` — checks version string and template directory
- [ ] `scripts/verify_template.sh` — checks all required files exist in base_2d
- [ ] `scripts/test_export.sh` — runs headless export and validates output
- [ ] `godot/templates/base_2d/` directory — the template itself
- [ ] `frontend/next.config.ts` — scaffold with COOP/COEP headers
- [ ] No pytest infrastructure needed for Phase 1 (all tests are shell scripts or manual)

---

## Sources

### Primary (HIGH confidence)

- SourceForge Godot 4.5.1 mirror — exact filenames, sizes, SHA1 checksums confirmed:
  `https://sourceforge.net/projects/godot-engine.mirror/files/4.5.1-stable/`
- GitHub Godot releases — release date (Oct 15 2024), release notes, commit hash:
  `https://github.com/godotengine/godot/releases/tag/4.5.1-stable`
- Godot official download archive — confirmed 4.5.1 is available:
  `https://godotengine.org/download/archive/4.5.1-stable/`
- Godot issue #83042 + PR #89234 — confirmed non-zero exit code on export failure fixed in Godot 4.3:
  `https://github.com/godotengine/godot/issues/83042`
- MDN SharedArrayBuffer — COOP/COEP requirement is a web standard:
  `https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cross-Origin-Embedder-Policy`
- Project STACK.md + ARCHITECTURE.md + PITFALLS.md — previously researched, HIGH confidence for this project's architecture decisions

### Secondary (MEDIUM confidence)

- Community CI examples (abarichello/godot-ci, chickensoft-games/setup-godot) — export template path format `4.5.1.stable`, Linux path `~/.local/share/godot/export_templates/`
- Search results consensus — macOS export template path is `~/Library/Application Support/Godot/export_templates/`
- Godot 4 command line tutorial — `--headless --export-release "Web"` syntax confirmed across multiple community CI examples
- godotshaders.com — canvas_item shader library source for pixel_art, glow, scanlines shaders

### Tertiary (LOW confidence — verify during implementation)

- macOS export template exact path — multiple sources say `~/Library/Application Support/Godot/export_templates/` but not confirmed from official Godot docs directly
- physical_keycode integer values for input actions — derived from training knowledge; use Godot editor to generate the actual values
- .tpz internal directory structure `templates/` prefix — from community CI scripts; verify with `unzip -l` before extraction

---

## Metadata

**Confidence breakdown:**
- Godot 4.5.1 release artifacts: HIGH — confirmed from multiple official and mirror sources
- macOS setup procedure: MEDIUM — binary/CLI confirmed; export template path from community sources, not official docs
- Template asset structure: HIGH — GDScript 4 syntax, .gdshader format, Gradient resource format all well-documented
- Input map format: MEDIUM — syntax confirmed; physical_keycode values need editor verification
- COOP/COEP headers: HIGH — web standard, Next.js headers() pattern is straightforward

**Research date:** 2026-03-13
**Valid until:** 2026-06-13 (stable; Godot 4.5.1 is a fixed release, not a moving target)
