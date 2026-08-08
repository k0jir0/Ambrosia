#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = ROOT / "packages" / "cli"
SDK_PATH = ROOT / "packages" / "sdk-python"
API_PATH = ROOT / "services" / "api"
OUTPUT_PATH = ROOT / "apps" / "web" / "src" / "generated" / "cli-guide-registry.json"

sys.path.insert(0, str(CLI_PATH))
sys.path.insert(0, str(SDK_PATH))
sys.path.insert(0, str(API_PATH))

from ambrosia_cli.guide_registry import QUALIFIED_READ_CONTRACTS  # noqa: E402
from ambrosia_cli.main import get_command_catalog  # noqa: E402
from app.main import app  # type: ignore[import-not-found]  # noqa: E402


def build_registry() -> list[dict[str, object]]:
    catalog = get_command_catalog()
    commands = {str(entry["command"]) for entry in catalog}
    missing_commands = sorted(set(QUALIFIED_READ_CONTRACTS) - commands)
    if missing_commands:
        raise RuntimeError(f"CLI Guide references commands missing from argparse: {missing_commands}")

    openapi_paths = set(app.openapi()["paths"])
    missing_paths = sorted(set(QUALIFIED_READ_CONTRACTS.values()) - openapi_paths)
    if missing_paths:
        raise RuntimeError(f"Qualified CLI Guide endpoints missing from OpenAPI: {missing_paths}")
    return catalog


def main() -> int:
    registry = build_registry()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)} ({len(registry)} parser commands)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())