"""POLISH-9-SMOKE-TEST: Run the lightweight production smoke suite.

Usage:
    python scripts/smoke-test.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    command = [sys.executable, "-m", "pytest", "tests/smoke.py", "--tb=no"]
    return subprocess.call(command, cwd=project_root)


if __name__ == "__main__":
    raise SystemExit(main())
