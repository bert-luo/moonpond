#!/usr/bin/env bash
# Checks that all required files exist in godot/templates/base_2d/
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_DIR="${REPO_ROOT}/godot/templates/base_2d"
PASS=0
FAIL=0

check_file() {
  local path="$1"
  if [[ -f "${TEMPLATE_DIR}/${path}" ]]; then
    echo "OK: ${path}"
    ((PASS++)) || true
  else
    echo "MISSING: ${path}"
    ((FAIL++)) || true
  fi
}

echo "==> Verifying base_2d template files..."

# Core project files
check_file "project.godot"
check_file "export_presets.cfg"
check_file "Main.tscn"
check_file "game_manager.gd"
check_file "default_bus_layout.tres"

# Shaders (TMPL-02)
check_file "assets/shaders/pixel_art.gdshader"
check_file "assets/shaders/glow.gdshader"
check_file "assets/shaders/scanlines.gdshader"
check_file "assets/shaders/chromatic_aberration.gdshader"
check_file "assets/shaders/screen_distortion.gdshader"

# Particle scenes (TMPL-03)
check_file "assets/particles/explosion.tscn"
check_file "assets/particles/dust.tscn"
check_file "assets/particles/sparkle.tscn"
check_file "assets/particles/trail.tscn"

# Palette resources (TMPL-04)
check_file "assets/palettes/neon.tres"
check_file "assets/palettes/retro.tres"
check_file "assets/palettes/pastel.tres"
check_file "assets/palettes/monochrome.tres"

# Control snippets (TMPL-06)
check_file "assets/control_snippets/mouse_follow.gd"
check_file "assets/control_snippets/click_to_move.gd"
check_file "assets/control_snippets/drag.gd"
check_file "assets/control_snippets/point_and_shoot.gd"

echo ""
echo "Results: ${PASS} present, ${FAIL} missing"
if [[ "$FAIL" -gt 0 ]]; then
  echo "verify_template.sh: FAILED"
  exit 1
fi
echo "verify_template.sh: PASSED"
