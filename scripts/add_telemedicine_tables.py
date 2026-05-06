from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.automation_tables import ensure_automation_tables


def main() -> int:
    ensure_automation_tables()
    print("Telemedicine and AI automation tables ensured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
