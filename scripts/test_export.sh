#!/usr/bin/env bash
# Runs headless WASM export of base_2d template and validates output
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_DIR="${REPO_ROOT}/godot/templates/base_2d"
OUTPUT_DIR="/tmp/moonpond_test_export"
OUTPUT_HTML="${OUTPUT_DIR}/index.html"
WASM_FILE="${OUTPUT_DIR}/index.wasm"
MIN_WASM_SIZE=500000  # 500KB

echo "==> Verifying Godot binary..."
if ! command -v godot &>/dev/null; then
  echo "ERROR: 'godot' not found. Run scripts/setup_godot.sh first."
  exit 1
fi

echo "==> Verifying base_2d template exists..."
if [[ ! -f "${TEMPLATE_DIR}/project.godot" ]]; then
  echo "ERROR: project.godot not found at ${TEMPLATE_DIR}"
  exit 1
fi

echo "==> Pre-warming .godot import cache (workaround for headless freeze bug)..."
# Issue #95287: headless export may freeze without import cache; build it first
godot --headless --editor --quit --path "$TEMPLATE_DIR" 2>&1 | tail -5 || true

echo "==> Running headless export..."
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

godot --headless \
  --export-release "Web" \
  "$OUTPUT_HTML" \
  --path "$TEMPLATE_DIR" 2>&1 | tee /tmp/godot_export_log.txt

echo "==> Validating output..."
if [[ ! -f "$WASM_FILE" ]]; then
  echo "ERROR: No .wasm file produced at ${WASM_FILE}"
  echo "Export log:"
  cat /tmp/godot_export_log.txt
  exit 1
fi

WASM_SIZE=$(stat -f%z "$WASM_FILE" 2>/dev/null || stat -c%s "$WASM_FILE")
if [[ "$WASM_SIZE" -lt "$MIN_WASM_SIZE" ]]; then
  echo "ERROR: .wasm is suspiciously small: ${WASM_SIZE} bytes (expected > ${MIN_WASM_SIZE})"
  exit 1
fi

# Check export log for ERROR: lines (belt-and-suspenders beyond exit code)
if grep -q "^ERROR:" /tmp/godot_export_log.txt; then
  echo "ERROR: Godot reported errors during export:"
  grep "^ERROR:" /tmp/godot_export_log.txt
  exit 1
fi

echo "OK: WASM export successful — ${WASM_SIZE} bytes"
echo "Output files:"
ls -lh "$OUTPUT_DIR"
echo "test_export.sh: PASSED"
