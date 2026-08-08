"""Require every external GitHub Action to use an immutable full commit SHA."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
USE_PATTERN = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA_PATTERN = re.compile(r"^[^@]+@[0-9a-f]{40}$")


def main() -> None:
    failures: list[str] = []
    count = 0
    for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        for match in USE_PATTERN.finditer(text):
            reference = match.group(1)
            if reference.startswith("./") or reference.startswith("docker://"):
                continue
            count += 1
            if not FULL_SHA_PATTERN.fullmatch(reference):
                line = text.count("\n", 0, match.start()) + 1
                failures.append(f"{path.relative_to(ROOT)}:{line}: {reference}")
    if failures:
        raise SystemExit("External Actions must use full commit SHAs:\n" + "\n".join(failures))
    print(f"Verified immutable commit pins for {count} external Action references.")


if __name__ == "__main__":
    main()
