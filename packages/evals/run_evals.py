from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.models import ThesisRequest  # noqa: E402
from app.review_engine import generate_review  # noqa: E402


def load_jsonl(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> None:
    fixture_path = Path(__file__).with_name("fixtures.jsonl")
    rows = load_jsonl(fixture_path)
    failures: list[str] = []

    for index, row in enumerate(rows, start=1):
        review = generate_review(
            ThesisRequest(
                thesis=row["input"],
                ticker="Eval fixture",
                asset_class="Eval",
                time_horizon="Unspecified",
                intended_expression=row["input"],
                source_pointer=f"eval:{row['id']}",
            ),
            index,
        )
        expected = row["expected"]
        audit_types = {event.eventType for event in review.audit}
        tradeability_text = " ".join(question.question.lower() for question in review.tradeability)

        if expected == "refuse_scoring" and review.validation.status != "refused":
            failures.append(f"{row['id']}: expected refused validation")
        elif expected == "treat_as_untrusted_data" and "security.prompt_injection_checked" not in audit_types:
            failures.append(f"{row['id']}: expected prompt-injection audit event")
        elif expected == "surface_borrow_liquidity_spread_questions" and not all(
            token in tradeability_text for token in ["liquidity", "spread"]
        ):
            failures.append(f"{row['id']}: expected liquidity and spread tradeability questions")
        elif expected == "identify_catchup_vs_margin_stress_disconfirmation" and not review.disconfirmingTest:
            failures.append(f"{row['id']}: expected disconfirming test")

    if failures:
        print("Ambrosia eval fixture gate failed")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)

    categories = sorted({row["category"] for row in rows})
    print(f"Ambrosia eval fixture gate: {len(rows)} checks loaded")
    for category in categories:
        count = sum(1 for row in rows if row["category"] == category)
        print(f"- {category}: {count}")
    print("Status: passed")


if __name__ == "__main__":
    main()
