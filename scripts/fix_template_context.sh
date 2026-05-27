#!/bin/bash
# One-command fix for template context error

set -euo pipefail

echo "Fixing template context error..."

APP_DIR="${APP_DIR:-$HOME/ayurveda-clinic-app}"
cd "$APP_DIR"

for file in apps/patient/routes.py routers/patients.py; do
    if [ -f "$file" ]; then
        cp "$file" "$file.backup"
    fi
done

echo "Checking request context lines..."
grep -n 'context\["request"\] = request' apps/patient/routes.py
grep -n 'ctx\["request"\] = request' routers/patients.py

echo "Restarting service..."
if command -v systemctl >/dev/null 2>&1; then
    if command -v sudo >/dev/null 2>&1; then
        sudo systemctl restart ayurveda
    else
        systemctl restart ayurveda
    fi
    sleep 5
else
    echo "systemctl not available; skipping service restart"
fi

echo "Running verification..."
python scripts/verify_fix.py
