#!/usr/bin/env bash
set -euo pipefail

if [ ! -d .git ]; then
  echo "Run this script from the project root."
  exit 1
fi

echo "Running tests before deploy..."
pytest -q

echo "Pushing current branch..."
git push

if [ -n "${RENDER_DEPLOY_HOOK_URL:-}" ]; then
  echo "Triggering Render deploy hook..."
  curl -fsSL -X POST "$RENDER_DEPLOY_HOOK_URL"
else
  echo "RENDER_DEPLOY_HOOK_URL is not set."
  echo "If auto-deploy is enabled in Render, the git push is enough."
fi
