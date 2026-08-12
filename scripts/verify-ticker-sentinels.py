from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = tuple((ROOT / "apps").glob("*/src")) + (ROOT / "services" / "api" / "app",)
SENTINELS = r"SAMPLE|DEMO|TEST|TICKER|SYMBOL|UNKNOWN|UNSPECIFIED"
ASSIGNMENT = re.compile(rf"ticker\s*[:=]\s*[\"'](?:{SENTINELS})[\"']", re.IGNORECASE)

violations: list[str] = []
for source_root in SOURCE_ROOTS:
    for path in source_root.rglob("*"):
        excluded = {".next", "node_modules", "dist", "build", "__tests__"}
        if not path.is_file() or path.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx"} or excluded.intersection(path.parts):
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ASSIGNMENT.search(line):
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")

if violations:
    raise SystemExit("Reserved ticker assignment(s) found:\n" + "\n".join(violations))

repair = (ROOT / "infra/db/migrations/V0010__verified_instrument_registry.sql").read_text(encoding="utf-8")
if "UPDATE guided_samples" not in repair or "instrument_reference" not in repair:
    raise SystemExit("V0010 must repair guided samples and create the instrument registry")

print("Ticker sentinel guard passed")
