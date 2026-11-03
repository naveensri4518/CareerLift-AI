#!/usr/bin/env bash
set -euo pipefail
cd /mnt/c/Users/Naveensri/Downloads/Madurai-TamilNadu-kiro
export CAREERLIFT_MODEL_MODE=mock
export CAREERLIFT_DB=./careerlift-shots.db
export CAREERLIFT_AUTH_PEPPER=change-me-locally
export CAREERLIFT_CORS_ORIGINS="http://localhost:5174,http://127.0.0.1:5174"
exec ~/.strands-ship/venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8001
