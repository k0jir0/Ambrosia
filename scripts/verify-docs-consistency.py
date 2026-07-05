#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI_README = ROOT / "packages" / "cli" / "README.md"
SDK_README = ROOT / "packages" / "sdk-python" / "README.md"
MATRIX_DOC = ROOT / "docs" / "roadmap" / "index85-evidence-matrix.md"


REQUIRED_CLI_TERMS = [
    "ambrosia relay evaluate",
    "ambrosia signals create",
    "ambrosia backtests run",
    "ambrosia paper-trades create",
    "ambrosia enterprise service-account",
    "ambrosia enterprise audit-export",
]

REQUIRED_SDK_TERMS = [
    "create_review",
    "relay_evaluate",
    "create_signal",
    "run_backtest",
    "create_paper_trade",
    "create_service_account",
    "create_audit_export",
]


def _assert_contains(path: Path, terms: list[str], errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"Missing documentation file: {path.relative_to(ROOT).as_posix()}")
        return
    text = path.read_text(encoding="utf-8")
    for term in terms:
        if term not in text:
            errors.append(f"{path.relative_to(ROOT).as_posix()} missing term: {term}")


def main() -> int:
    errors: list[str] = []
    _assert_contains(CLI_README, REQUIRED_CLI_TERMS, errors)
    _assert_contains(SDK_README, REQUIRED_SDK_TERMS, errors)

    if not MATRIX_DOC.exists():
        errors.append("Missing docs/roadmap/index85-evidence-matrix.md")

    if errors:
        print("Documentation consistency verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Documentation consistency verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
