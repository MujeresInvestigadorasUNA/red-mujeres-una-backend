import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.main import app


def main() -> None:
    docs_dir = ROOT_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    output_file = docs_dir / "openapi.json"
    schema = app.openapi()

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(schema, file, ensure_ascii=False, indent=2)

    print(f"OpenAPI exportado en: {output_file}")


if __name__ == "__main__":
    main()