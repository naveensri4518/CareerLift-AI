#!/usr/bin/env bash
# Run the CareerLift backend for local dev: mock mode (no AWS), port 8000, matching `npm run dev` (5173).
# NOTE: started from WSL, this backend cannot reach the Windows Docker daemon, so the Coding Arena's
# Run/Submit will show "sandbox unavailable". Browsing problems works. For live code execution, run the
# backend from an environment that can reach the Docker socket.
set -euo pipefail
cd /mnt/c/Users/Naveensri/Downloads/Madurai-TamilNadu-kiro
export CAREERLIFT_MODEL_MODE=mock
export CAREERLIFT_DB=./careerlift.db
export CAREERLIFT_AUTH_PEPPER=change-me-locally
export CAREERLIFT_CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
# Bind 0.0.0.0 INSIDE WSL (not 127.0.0.1): WSL2's localhost-forwarding reliably exposes an all-interfaces
# listener to Windows at localhost:8000 / 127.0.0.1:8000, whereas a WSL 127.0.0.1-only bind is only
# partially reachable from Windows (browsers get ERR_CONNECTION_REFUSED). WSL2's network is host-only by
# default, so this is not exposed to the public internet.
exec ~/.strands-ship/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
