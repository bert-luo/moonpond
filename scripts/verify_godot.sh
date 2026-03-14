#!/usr/bin/env bash
# Verifies Godot 4.5.1 binary and export templates are installed correctly
set -euo pipefail
GODOT_VERSION="4.5.1"
TEMPLATES_DIR="$HOME/Library/Application Support/Godot/export_templates/${GODOT_VERSION}.stable"

echo "==> Checking godot binary..."
if ! command -v godot &>/dev/null; then
  echo "ERROR: 'godot' not found in PATH. Run scripts/setup_godot.sh first."
  exit 1
fi

INSTALLED_VERSION=$(godot --headless --version 2>/dev/null || echo "FAILED")
if [[ "$INSTALLED_VERSION" != "${GODOT_VERSION}"* ]]; then
  echo "ERROR: Expected Godot ${GODOT_VERSION}, found: ${INSTALLED_VERSION}"
  exit 1
fi
echo "OK: Godot version: ${INSTALLED_VERSION}"

echo "==> Checking export templates..."
if [[ ! -d "$TEMPLATES_DIR" ]]; then
  echo "ERROR: Export templates directory not found: ${TEMPLATES_DIR}"
  echo "Hint: Directory name must be '${GODOT_VERSION}.stable' (dot before stable, not hyphen)"
  exit 1
fi

# Check for web export templates
WEB_DEBUG="${TEMPLATES_DIR}/web_debug.zip"
WEB_RELEASE="${TEMPLATES_DIR}/web_release.zip"
if [[ ! -f "$WEB_DEBUG" ]] || [[ ! -f "$WEB_RELEASE" ]]; then
  echo "ERROR: Web export templates missing in ${TEMPLATES_DIR}"
  echo "Found: $(ls "$TEMPLATES_DIR" | head -10)"
  exit 1
fi
echo "OK: Web export templates present (web_debug.zip, web_release.zip)"
echo "verify_godot.sh: PASSED"
