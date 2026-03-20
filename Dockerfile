# ==============================================================================
# Stage 1: Download and verify Godot 4.5.1-stable
# ==============================================================================
FROM debian:bookworm-slim AS godot

ARG TARGETARCH
ARG GODOT_VERSION=4.5.1
ARG GODOT_VERSION_TAG=${GODOT_VERSION}-stable

# Template dir uses dot notation: 4.5.1.stable (not hyphen)
ARG TEMPLATES_DIR=/root/.local/share/godot/export_templates/${GODOT_VERSION}.stable

# SHA-512 checksums from official GitHub release (per architecture)
ARG GODOT_SHA512_AMD64=5bccbed65a94b82c7c319fdb15719ee8113a6e503976cc54e16f1c61fe95f3d74e5e40b8449b5bb89ff7f424574c20af01a4f5ef08b389e4dc338b245185b0b9
ARG GODOT_SHA512_ARM64=9d55e9cdccaa4b6528d0b39824d51c47987667babffbab7f83b05fba2ece842a59752b84128332421c9d261fe06846b88480f3b0171af255ea99383d3bc96b2c
ARG TEMPLATES_SHA512=8a65c73541184fbcf1a7afedb37c9c15ed0f3babdaafe36ff47ccc515548ac84bc7563ba5b94c253e6085b121ac608b7e03d35dfc0b2c8c690a646a8755b57e5

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    ca-certificates \
    # Godot runtime deps (needed even in headless mode)
    libgl1 \
    libglib2.0-0 \
    libx11-6 \
    libxcursor1 \
    libxi6 \
    libxinerama1 \
    libxrandr2 \
    libxrender1 \
    libfontconfig1 \
    libasound2 \
    libdbus-1-3 \
    libpulse0 \
    libudev1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

# Map Docker TARGETARCH to Godot arch naming and select correct checksum
# Docker: amd64/arm64  ->  Godot: x86_64/arm64
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        GODOT_ARCH="arm64"; \
        GODOT_SHA512="$GODOT_SHA512_ARM64"; \
    else \
        GODOT_ARCH="x86_64"; \
        GODOT_SHA512="$GODOT_SHA512_AMD64"; \
    fi \
    && GODOT_ZIP="Godot_v${GODOT_VERSION_TAG}_linux.${GODOT_ARCH}.zip" \
    && GODOT_BIN_NAME="Godot_v${GODOT_VERSION_TAG}_linux.${GODOT_ARCH}" \
    && echo "Downloading Godot for ${TARGETARCH} (${GODOT_ARCH})..." \
    && curl -L -o godot.zip \
        "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION_TAG}/${GODOT_ZIP}" \
    && echo "${GODOT_SHA512}  godot.zip" | sha512sum -c - \
    && unzip godot.zip \
    && mv "${GODOT_BIN_NAME}" /usr/local/bin/godot \
    && chmod +x /usr/local/bin/godot \
    && rm godot.zip

# Verify Godot binary version
RUN INSTALLED=$(/usr/local/bin/godot --headless --version 2>/dev/null | head -1) \
    && echo "Installed Godot version: ${INSTALLED}" \
    && echo "${INSTALLED}" | grep -q "^${GODOT_VERSION}" \
    || (echo "ERROR: Expected ${GODOT_VERSION}, got ${INSTALLED}" && exit 1)

# Download and install export templates (architecture-independent)
RUN curl -L -o templates.tpz \
    "https://github.com/godotengine/godot/releases/download/${GODOT_VERSION_TAG}/Godot_v${GODOT_VERSION_TAG}_export_templates.tpz" \
    && echo "${TEMPLATES_SHA512}  templates.tpz" | sha512sum -c - \
    && mkdir -p "${TEMPLATES_DIR}" \
    && unzip templates.tpz -d /tmp/tpl_extract \
    && mv /tmp/tpl_extract/templates/* "${TEMPLATES_DIR}/" \
    && rm -rf templates.tpz /tmp/tpl_extract

# Verify export templates contain required web files
RUN test -f "${TEMPLATES_DIR}/web_release.zip" \
    && test -f "${TEMPLATES_DIR}/web_debug.zip" \
    && echo "Export templates verified: web_release.zip and web_debug.zip present" \
    || (echo "ERROR: Missing web export templates" && ls -la "${TEMPLATES_DIR}/" && exit 1)


# ==============================================================================
# Stage 2: Python application
# ==============================================================================
FROM python:3.12-slim AS app

ARG GODOT_VERSION=4.5.1
ARG TEMPLATES_DIR=/root/.local/share/godot/export_templates/${GODOT_VERSION}.stable

# Godot runtime deps (needed even in headless mode)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libx11-6 \
    libxcursor1 \
    libxi6 \
    libxinerama1 \
    libxrandr2 \
    libxrender1 \
    libfontconfig1 \
    libasound2 \
    libdbus-1-3 \
    libpulse0 \
    libudev1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Godot binary from stage 1
COPY --from=godot /usr/local/bin/godot /usr/local/bin/godot

# Copy export templates from stage 1
COPY --from=godot ${TEMPLATES_DIR} ${TEMPLATES_DIR}

# Set Godot env var so runner.py finds the binary
ENV GODOT_BIN=/usr/local/bin/godot

# Install uv for fast Python dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install Python dependencies (cached layer — only re-runs when pyproject.toml changes)
COPY backend/pyproject.toml backend/uv.lock* ./backend/
RUN cd backend && uv pip install --system -e ".[dev]" 2>/dev/null || uv pip install --system -e .

# Copy backend source
COPY backend/ ./backend/

# Copy Godot project templates (base_2d, base_3d)
COPY godot/templates/ ./godot/templates/

# Create games output directory
RUN mkdir -p /app/games

EXPOSE 8000

WORKDIR /app/backend

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
