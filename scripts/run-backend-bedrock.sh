#!/usr/bin/env bash
# Launch the CareerLift AI backend in BEDROCK mode using the WSL-native AWS SSO profile.
# Prerequisite (one-time per ~8h session): `aws sso login --profile career-lift` in WSL.
# Nothing here creates AWS resources; scoring an answer makes billable Bedrock/Translate calls.
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$HOME/.local/bin:$PATH"          # WSL-native aws CLI
export AWS_PROFILE="career-lift"
export AWS_REGION="us-east-1"
export CAREERLIFT_MODEL_MODE="bedrock"         # real Amazon Nova 2 Lite + Amazon Translate
export CAREERLIFT_DB="./careerlift.db"
export CAREERLIFT_AUTH_PEPPER="${CAREERLIFT_AUTH_PEPPER:-change-me-locally}"

# Fail fast with a friendly message if the SSO session is not active.
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  echo "AWS SSO session not active. Run:  aws sso login --profile career-lift" >&2
  exit 1
fi

exec "$HOME/.strands-ship/venv/bin/python" -m uvicorn api.main:app --host 127.0.0.1 --port 8000
