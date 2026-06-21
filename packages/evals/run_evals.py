from __future__ import annotations

import json
from pathlib import Path


def load_jsonl(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    fixture_path = Path(__file__).with_name("fixtures.jsonl")
    rows = load_jsonl(fixture_path)
    categories = sorted({row["category"] for row in rows})
    print(f"Ambrosia eval fixture gate: {len(rows)} checks loaded")
    for category in categories:
        count = sum(1 for row in rows if row["category"] == category)
        print(f"- {category}: {count}")
    print("Status: ready for CI integration")


if __name__ == "__main__":
    main()