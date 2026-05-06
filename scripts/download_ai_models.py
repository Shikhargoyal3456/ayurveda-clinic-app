from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    placeholders = {
        "skin_disease_model.h5": "placeholder skin model",
        "eye_disease_model.h5": "placeholder eye model",
        "throat_infection_model.h5": "placeholder throat model",
    }
    for filename, content in placeholders.items():
        path = MODELS_DIR / filename
        if not path.exists():
            path.write_text(content, encoding="utf-8")
    print("AI model placeholders ready.")
    for filename in placeholders:
        print(f"- {filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
