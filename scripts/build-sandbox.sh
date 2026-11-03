#!/usr/bin/env bash
# Build the Phase 2 Coding Arena sandbox image. Run this once (needs a running Docker daemon) before
# the Coding Arena can execute code. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."
docker build -t careerlift-coding-sandbox:latest -f docker/coding-sandbox.Dockerfile docker
echo "Built careerlift-coding-sandbox:latest"
