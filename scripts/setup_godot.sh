#!/usr/bin/env bash
# Downloads Godot 4.5.1-stable for macOS + export templates, installs to godot/bin/
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
GODOT_VERSION="4.5.1"
GODOT_VERSION_TAG="${GODOT_VERSION}-stable"
GODOT_INSTALL_DIR="${REPO_ROOT}/godot/bin"
BASE_URL="https://github.com/godotengine/godot/releases/download/${GODOT_VERSION_TAG}"
MACOS_ZIP="Godot_v${GODOT_VERSION_TAG}_macos.universal.zip"
TEMPLATES_TPZ="Godot_v${GODOT_VERSION_TAG}_export_templates.tpz"
# macOS export templates path (dot-separated: 4.5.1.stable NOT 4.5.1-stable)
TEMPLATES_DIR="$HOME/Library/Application Support/Godot/export_templates/${GODOT_VERSION}.stable"

echo "==> Downloading Godot ${GODOT_VERSION_TAG} macOS binary..."
curl -L --progress-bar -o "/tmp/${MACOS_ZIP}" "${BASE_URL}/${MACOS_ZIP}"
unzip -o "/tmp/${MACOS_ZIP}" -d "$GODOT_INSTALL_DIR"

echo "==> Removing macOS quarantine attribute..."
xattr -dr com.apple.quarantine "$GODOT_INSTALL_DIR/Godot.app" 2>/dev/null || true

echo "==> Creating /usr/local/bin/godot symlink..."
sudo ln -sf "$GODOT_INSTALL_DIR/Godot.app/Contents/MacOS/Godot" /usr/local/bin/godot

echo "==> Downloading export templates (1.4 GB — this will take a while)..."
curl -L --progress-bar -o "/tmp/${TEMPLATES_TPZ}" "${BASE_URL}/${TEMPLATES_TPZ}"

echo "==> Installing export templates to ${TEMPLATES_DIR}..."
mkdir -p "$TEMPLATES_DIR"
cp "/tmp/${TEMPLATES_TPZ}" /tmp/godot_templates.zip
# Inspect contents to confirm templates/ prefix
unzip -l /tmp/godot_templates.zip | head -20
rm -rf /tmp/godot_templates_extracted/
unzip -o /tmp/godot_templates.zip -d /tmp/godot_templates_extracted/
# The TPZ contains a templates/ subdirectory — move its contents directly
mv /tmp/godot_templates_extracted/templates/* "$TEMPLATES_DIR/"

echo "==> Verifying installation..."
INSTALLED_VERSION=$(godot --headless --version 2>/dev/null || echo "FAILED")
if [[ "$INSTALLED_VERSION" != "${GODOT_VERSION}"* ]]; then
  echo "ERROR: Expected version ${GODOT_VERSION}, got: ${INSTALLED_VERSION}"
  exit 1
fi
echo "Godot ${INSTALLED_VERSION} installed successfully."
echo "Export templates installed to: ${TEMPLATES_DIR}"
ls "$TEMPLATES_DIR" | head -5
