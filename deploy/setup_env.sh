#!/bin/bash
# /workspace/setup_env.sh — idempotent, run on every container start
# Creates a persistent Python venv on /workspace (NVMe) with pinned packages
VENV=/workspace/venv
REQ=/workspace/requirements-training.txt

# Create venv if missing (inherits pytorch/cuda from base image)
if [ ! -d "$VENV" ]; then
    echo "[setup] Creating persistent venv..."
    /opt/conda/bin/python -m venv "$VENV" --system-site-packages
fi

# Install/verify pinned packages
"$VENV/bin/pip" install -q -r "$REQ" 2>/dev/null

echo "[setup] Environment ready. Python: $($VENV/bin/python --version)"
