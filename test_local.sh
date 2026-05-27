#!/bin/bash
# Test the app locally before deployment

set -euo pipefail

echo "Testing Kash AI locally..."

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    PYTHON_BIN="python"
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    "${PYTHON_BIN}" -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

echo "Running tests..."
pytest -q

echo "Starting server..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!

cleanup() {
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

sleep 5

echo "Testing endpoints..."
curl -f http://localhost:8000/health
curl -f http://localhost:8000/

echo "Local test complete."
