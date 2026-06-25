from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.models import DecisionPacket, ThesisRequest  # noqa: E402
from app.coordinator import run_specialists  # noqa: E402
from app.providers import ProviderMode, resolve_provider  # noqa: E402
from app.review_engine import generate_review  # noqa: E402

FIXTURE_PATH = Path(__file__).with_name("fixtures.jsonl")

DEFAULT_MODES: tuple[ProviderMode, ...] = (
    "deterministic",
    "hosted",
    "ollama",
    "hybrid",
)

COST_PROXY_PER_ROLE = {
    "deterministic": 0.0,
    "ollama": 0.1,
    "hosted": 1.0,
    "hybrid": 0.6,
}


@dataclass
class ModeAggregate:
    requestedMode: str
    selectedProvider: str
    selectedProviderType: str
    fallbackChain: list[str]
    reason: str
    cases: int
    fallbackRuns: int
    avgLatencyMs: float
    p95LatencyMs: float
    avgQualityScore: float
    avgRequestedCostProxyUnits: float
    avgEffectiveCostProxyUnits: float


@dataclass
class AblationReport:
    generatedAt: str
    fixtures: int
    modes: list[ModeAggregate]


def load_jsonl(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def review_to_packet(review_id: int, thesis: str) -> DecisionPacket:
    review = generate_review(
        ThesisRequest(
            thesis=thesis,
            ticker="ABLT",
            asset_class="Equity",
            time_horizon="Swing",
            intended_expression=thesis,
            source_pointer=f"eval:ablation:{review_id}",
        ),
        review_id,
    )
    return DecisionPacket(
        id=f"pkt-{uuid4().hex[:10]}",
        schemaVersion="packet.v1",
        workflowVersion="quant-agent.v1",
        title=f"Ablation packet {review.ticker}",
        thesis=review.thesis,
        ticker=review.ticker,
        assetClass=review.assetClass,
        timeHorizon=review.timeHorizon,
        intendedExpression=review.intendedExpression,
        status=review.status,
        decisionState=review.decisionState,
        confidence=review.confidence,
        trialCountImpact=review.trialCountImpact,
        followUpDate=review.followUpDate,
        createdAt=review.createdAt,
        claims=review.claims,
        strongestCritique=review.strongestCritique,
        disconfirmingTest=review.disconfirmingTest,
        historicalAnalogue=review.historicalAnalogue,
        validation=review.validation,
        tradeability=review.tradeability,
        sources=review.sources,
        audit=review.audit,
    )


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = int(round((len(ordered) - 1) * pct))
    return ordered[max(0, min(rank, len(ordered) - 1))]


def aggregate_mode(mode: ProviderMode, rows: list[dict[str, str]]) -> ModeAggregate:
    provider = resolve_provider(mode)
    latencies_ms: list[float] = []
    quality_scores: list[float] = []
    fallback_runs = 0

    for index, row in enumerate(rows, start=1):
        packet = review_to_packet(index, row["input"])
        start = perf_counter()
        outputs, runtime_fallback_used = run_specialists(packet, provider)
        elapsed_ms = (perf_counter() - start) * 1000.0
        latencies_ms.append(elapsed_ms)

        role_scores = [
            output.score
            for output in outputs.values()
            if output is not None and output.score is not None
        ]
        if role_scores:
            quality_scores.append(sum(role_scores) / len(role_scores))

        if runtime_fallback_used:
            fallback_runs += 1

    avg_latency = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
    # Cost proxies reflect relative spend risk, not real billing.
    requested_cost_proxy = COST_PROXY_PER_ROLE.get(mode, 0.0) * 10
    effective_cost_proxy = COST_PROXY_PER_ROLE.get(provider.provider_type, 0.0) * 10

    return ModeAggregate(
        requestedMode=mode,
        selectedProvider=provider.name,
        selectedProviderType=provider.provider_type,
        fallbackChain=provider.fallback_chain,
        reason=provider.reason,
        cases=len(rows),
        fallbackRuns=fallback_runs,
        avgLatencyMs=round(avg_latency, 2),
        p95LatencyMs=round(percentile(latencies_ms, 0.95), 2),
        avgQualityScore=round(avg_quality, 2),
        avgRequestedCostProxyUnits=round(requested_cost_proxy, 2),
        avgEffectiveCostProxyUnits=round(effective_cost_proxy, 2),
    )


def build_markdown(report: AblationReport) -> str:
    lines: list[str] = []
    lines.append("# Provider Ablation Report")
    lines.append("")
    lines.append(f"Generated: {report.generatedAt}")
    lines.append(f"Fixtures evaluated: {report.fixtures}")
    lines.append("")
    lines.append("## Cost/Latency/Quality Tradeoff Matrix")
    lines.append("")
    lines.append("| Requested Mode | Selected Provider | Provider Type | Avg Latency (ms) | P95 Latency (ms) | Avg Quality | Requested Cost Proxy | Effective Cost Proxy | Fallback Runs / Cases |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for mode in report.modes:
        lines.append(
            "| "
            f"{mode.requestedMode} | {mode.selectedProvider} | {mode.selectedProviderType} | "
            f"{mode.avgLatencyMs} | {mode.p95LatencyMs} | {mode.avgQualityScore} | "
            f"{mode.avgRequestedCostProxyUnits} | {mode.avgEffectiveCostProxyUnits} | "
            f"{mode.fallbackRuns} / {mode.cases} |"
        )

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Cost proxy units are relative indicators (deterministic < ollama < hosted) and not cloud billing values.")
    lines.append("- Requested cost proxy reflects requested mode intent; effective cost proxy reflects resolved runtime provider.")
    lines.append("- Fallback runs indicate runtime degradations or unavailable provider configuration.")
    lines.append("- Quality score is the average of specialist role scores returned by coordinator output.")
    lines.append("")
    lines.append("## Provider Resolution")
    lines.append("")
    for mode in report.modes:
        lines.append(f"- {mode.requestedMode}: {mode.reason}")

    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run provider ablation matrix for Ambrosia evals.")
    parser.add_argument(
        "--output-json",
        default=str(ROOT / "artifacts" / "provider-ablation.json"),
        help="Path to write JSON artifact.",
    )
    parser.add_argument(
        "--output-md",
        default=str(ROOT / "artifacts" / "provider-ablation.md"),
        help="Path to write Markdown artifact.",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=["deterministic", "hosted", "ollama", "hybrid"],
        default=list(DEFAULT_MODES),
        help="Provider modes to compare.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixtures = load_jsonl(FIXTURE_PATH)

    aggregates = [aggregate_mode(mode, fixtures) for mode in args.modes]
    report = AblationReport(
        generatedAt=datetime.now(UTC).isoformat(),
        fixtures=len(fixtures),
        modes=aggregates,
    )

    output_json_path = Path(args.output_json)
    output_md_path = Path(args.output_md)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_md_path.parent.mkdir(parents=True, exist_ok=True)

    output_json_path.write_text(
        json.dumps(
            {
                "generatedAt": report.generatedAt,
                "fixtures": report.fixtures,
                "modes": [asdict(mode) for mode in report.modes],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output_md_path.write_text(build_markdown(report), encoding="utf-8")

    print(f"Wrote {output_json_path}")
    print(f"Wrote {output_md_path}")
    for mode in report.modes:
        print(
            f"- {mode.requestedMode}: provider={mode.selectedProvider} "
            f"latency={mode.avgLatencyMs}ms quality={mode.avgQualityScore} "
            f"requestedCostProxy={mode.avgRequestedCostProxyUnits} "
            f"effectiveCostProxy={mode.avgEffectiveCostProxyUnits} "
            f"fallback={mode.fallbackRuns}/{mode.cases}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
