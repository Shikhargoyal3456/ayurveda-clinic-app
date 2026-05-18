"""
Scan and optionally migrate legacy frontend patterns to modern Kash AI design tokens.

Usage:
    python scripts/migrate_to_modern_frontend.py --dry-run
    python scripts/migrate_to_modern_frontend.py --apply
"""

from __future__ import annotations

import argparse
from pathlib import Path


OLD_PATTERNS = {
    "col-md-": "modern-grid-col",
    "col-sm-": "modern-grid-col",
    "btn-primary": "modern-button",
    "panel-default": "modern-card",
    "well": "modern-card",
    "img-responsive": "modern-img",
    "form-control": "modern-input",
    "#337ab7": "var(--color-primary)",
    "#5bc0de": "var(--color-ai)",
    "#d9534f": "var(--color-danger)",
}

SCAN_ROOTS = [
    Path("templates"),
    Path("apps"),
    Path("shared"),
]


def scan_file(filepath: Path) -> list[str]:
    content = filepath.read_text(encoding="utf-8", errors="ignore")
    issues: list[str] = []
    for old, new in OLD_PATTERNS.items():
        if old in content:
            issues.append(f"Found '{old}' -> replace with '{new}'")
    return issues


def migrate_file(filepath: Path) -> bool:
    content = filepath.read_text(encoding="utf-8", errors="ignore")
    updated = content
    for old, new in OLD_PATTERNS.items():
        updated = updated.replace(old, new)
    if updated == content:
        return False
    filepath.write_text(updated, encoding="utf-8")
    return True


def iter_template_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*") if path.suffix in {".html", ".css", ".js"})
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan or migrate legacy frontend patterns.")
    parser.add_argument("--dry-run", action="store_true", help="Report files that still contain legacy patterns.")
    parser.add_argument("--apply", action="store_true", help="Apply simple string replacements in-place.")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.error("Choose --dry-run or --apply.")

    matches = 0
    migrations = 0

    for filepath in iter_template_files():
        issues = scan_file(filepath)
        if not issues:
            continue
        matches += 1
        print(f"\n[scan] {filepath}")
        for issue in issues:
            print(f"  - {issue}")
        if args.apply and migrate_file(filepath):
            migrations += 1
            print("  -> migrated")

    if not matches:
        print("No legacy frontend patterns found.")
        return 0

    print(f"\nScanned {matches} file(s) with legacy frontend patterns.")
    if args.apply:
        print(f"Migrated {migrations} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
