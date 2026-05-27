from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET_DIRS = ("routers", "routes", "apps")
IMPORT_LINE = "from shared.template_engine import render_template"


def update_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    text = original

    if "TemplateResponse(" not in text or "render_template(" in text:
        return False

    if "from shared.template_engine import render_template" not in text:
        lines = text.splitlines()
        insert_at = find_import_insert_index(lines)
        lines.insert(insert_at, IMPORT_LINE)
        text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")

    text = re.sub(
        r"(?P<prefix>\b)templates\.TemplateResponse\(\s*request\s*,",
        r"\g<prefix>render_template(templates, request,",
        text,
    )

    if text == original:
        return False

    path.write_text(text, encoding="utf-8")
    return True


def find_import_insert_index(lines: list[str]) -> int:
    insert_at = 0
    paren_depth = 0
    seen_import = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if seen_import:
                insert_at = index + 1
            continue
        if paren_depth > 0:
            paren_depth += line.count("(") - line.count(")")
            insert_at = index + 1
            continue
        if line.startswith("from ") or line.startswith("import "):
            seen_import = True
            paren_depth += line.count("(") - line.count(")")
            insert_at = index + 1
            continue
        break
    return insert_at


def main() -> int:
    parser = argparse.ArgumentParser(description="Replace direct TemplateResponse(request, ...) calls with render_template(...).")
    parser.add_argument("--check", action="store_true", help="Report files that would change without writing them.")
    args = parser.parse_args()

    changed: list[Path] = []
    for target_dir in TARGET_DIRS:
        base = ROOT / target_dir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            original = path.read_text(encoding="utf-8")
            updated = original

            if "TemplateResponse(" not in updated or "render_template(" in updated:
                continue

            if IMPORT_LINE not in updated:
                lines = updated.splitlines()
                insert_at = find_import_insert_index(lines)
                lines.insert(insert_at, IMPORT_LINE)
                updated = "\n".join(lines) + ("\n" if original.endswith("\n") else "")

            updated = re.sub(
                r"(?P<prefix>\b)templates\.TemplateResponse\(\s*request\s*,",
                r"\g<prefix>render_template(templates, request,",
                updated,
            )
            if updated == original:
                continue

            changed.append(path)
            if not args.check:
                path.write_text(updated, encoding="utf-8")

    for path in changed:
        print(path.relative_to(ROOT))

    if args.check and changed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
