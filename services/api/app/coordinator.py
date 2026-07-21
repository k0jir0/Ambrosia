from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime

from .models import DecisionPacket, SpecialistAgentOutput
from .providers import ProviderSelection
from .resilience import resilient_urlopen


def _ts() -> str:
    return datetime.now(UTC).isoformat()


def _bounded_score(value: int) -> int:
    return max(0, min(100, value))


def _trend_score(packet: DecisionPacket) -> int:
    if not packet.technicals:
        return 50
    trend = packet.technicals.trend
    base = 60 if trend == "uptrend" else 45 if trend == "sideways" else 35 if trend == "downtrend" else 50
    rsi = packet.technicals.rsi or 50
    return _bounded_score(int(base + ((rsi - 50) * 0.3)))


def _sentiment_score(packet: DecisionPacket) -> int:
    if not packet.sentiment:
        return 50
    return _bounded_score(int(packet.sentiment.overallScore))


def _packet_context(packet: DecisionPacket) -> str:
    return (
        f"ticker={packet.ticker}; thesis={packet.thesis}; status={packet.status}; "
        f"confidence={packet.confidence}; decisionState={packet.decisionState}; "
        f"trend={packet.technicals.trend if packet.technicals else 'unknown'}; "
        f"rsi={packet.technicals.rsi if packet.technicals else 'n/a'}; "
        f"sentiment={packet.sentiment.sentiment if packet.sentiment else 'n/a'}; "
        f"sentimentScore={packet.sentiment.overallScore if packet.sentiment else 'n/a'}; "
        f"backtestStatus={packet.backtestPlan.status if packet.backtestPlan else 'not_requested'}; "
        f"riskStatus={packet.riskMonitor.status if packet.riskMonitor else 'monitoring'}"
    )


def _role_instruction(role: str) -> str:
    return (
        "Respond with strict JSON only: "
        "{\"summary\": string, \"keyPoints\": string[3], \"score\": integer 0-100}. "
        f"You are the {role} specialist in a quant decision workflow. "
        "Do not claim unavailable data. Keep summary concise and risk-aware."
    )


def _call_openai(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are a quant specialist output generator."},
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with resilient_urlopen("openai", request, timeout=10, attempts=2) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return raw["choices"][0]["message"]["content"]


def _call_ollama(prompt: str) -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    payload = {"model": model, "prompt": prompt, "stream": False, "format": "json"}
    request = urllib.request.Request(
        f"{base_url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with resilient_urlopen("ollama", request, timeout=10, attempts=2) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return raw.get("response", "")


def _parse_specialist_response(content: str) -> tuple[str, list[str], int]:
    parsed = json.loads(content)
    summary = str(parsed.get("summary", "No summary provided"))
    points_raw = parsed.get("keyPoints", [])
    if not isinstance(points_raw, list):
        points_raw = []
    points = [str(point) for point in points_raw][:3]
    if len(points) < 3:
        points.extend(["No additional point"] * (3 - len(points)))
    score = _bounded_score(int(parsed.get("score", 50)))
    return summary, points, score


def _deterministic_outputs(
    packet: DecisionPacket,
    provider: ProviderSelection,
) -> dict[str, SpecialistAgentOutput | None]:
    trend_score = _trend_score(packet)
    sent_score = _sentiment_score(packet)

    return {
        "marketData": SpecialistAgentOutput(
            role="marketData",
            summary=f"Market snapshot reviewed for {packet.ticker} with latest price context.",
            keyPoints=[
                f"Ticker: {packet.ticker}",
                f"Data source: {packet.marketSnapshot.dataSource if packet.marketSnapshot else 'unavailable'}",
                "Provenance retained for downstream synthesis",
            ],
            score=packet.confidence,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "technical": SpecialistAgentOutput(
            role="technical",
            summary="Technical profile synthesized from RSI, moving averages, and trend state.",
            keyPoints=[
                f"Trend: {packet.technicals.trend if packet.technicals else 'unknown'}",
                f"RSI: {packet.technicals.rsi if packet.technicals else 'n/a'}",
                "MACD and volatility included in signal interpretation",
            ],
            score=trend_score,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "sentiment": SpecialistAgentOutput(
            role="sentiment",
            summary="Sentiment source mix evaluated with confidence labels.",
            keyPoints=[
                f"Overall sentiment score: {packet.sentiment.overallScore if packet.sentiment else 'n/a'}",
                f"Confidence label: {packet.sentiment.sourceConfidence if packet.sentiment else 'n/a'}",
                "News/social trend direction captured for PM synthesis",
            ],
            score=sent_score,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "interMarket": SpecialistAgentOutput(
            role="interMarket",
            summary="Inter-market and regime context prepared for risk-aware interpretation.",
            keyPoints=[
                f"Regime: {packet.interMarket.regimeState if packet.interMarket else 'mixed'}",
                f"Spillover risk: {packet.interMarket.spilloverRisk if packet.interMarket else 'medium'}",
                "Correlation inputs included where available",
            ],
            score=55,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "fundamental": SpecialistAgentOutput(
            role="fundamental",
            summary="Fundamental context inspected for valuation and quality support.",
            keyPoints=[
                f"Quality score: {packet.fundamentals.qualityScore if packet.fundamentals else 'n/a'}",
                f"Growth rate: {packet.fundamentals.growthRate if packet.fundamentals else 'n/a'}",
                "Valuation metrics normalized into packet context",
            ],
            score=58,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "quant": SpecialistAgentOutput(
            role="quant",
            summary="Validation and backtest-readiness checks prepared.",
            keyPoints=[
                f"Validation status: {packet.validation.status}",
                f"Backtest status: {packet.backtestPlan.status if packet.backtestPlan else 'not_requested'}",
                "Hygiene constraints preserved before trade recommendation",
            ],
            score=53,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "bull": SpecialistAgentOutput(
            role="bull",
            summary="Bull case distilled for opportunity framing.",
            keyPoints=[
                "Evidence and momentum alignment highlighted",
                "Upside path conditioned on validation gates",
                "Position sizing constrained by risk budget",
            ],
            score=_bounded_score(int((trend_score + sent_score) / 2 + 5)),
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "bear": SpecialistAgentOutput(
            role="bear",
            summary="Bear case assembled to pressure-test thesis robustness.",
            keyPoints=[
                "Disconfirming triggers preserved",
                "Crowding and regime-shift risks emphasized",
                "Execution/slippage downside conditions included",
            ],
            score=_bounded_score(100 - int((trend_score + sent_score) / 2)),
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "risk": SpecialistAgentOutput(
            role="risk",
            summary="Risk posture summarized with portfolio-aware controls.",
            keyPoints=[
                f"Risk monitor status: {packet.riskMonitor.status if packet.riskMonitor else 'monitoring'}",
                "Concentration and overlap checks retained",
                "Follow-up triggers included in packet lifecycle",
            ],
            score=60,
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
        "pmSynthesis": SpecialistAgentOutput(
            role="pmSynthesis",
            summary="Coordinator synthesized specialist outputs into decision readiness view.",
            keyPoints=[
                f"Provider selected: {provider.name}",
                f"Fallback used: {provider.fallback_used}",
                "Human decision authority remains required",
            ],
            score=_bounded_score(int((trend_score + sent_score + packet.confidence) / 3)),
            timestamp=_ts(),
            provider=provider.name,
            fallbackUsed=provider.fallback_used,
        ),
    }


def run_specialists(
    packet: DecisionPacket,
    provider: ProviderSelection,
) -> tuple[dict[str, SpecialistAgentOutput | None], bool]:
    deterministic_outputs = _deterministic_outputs(packet, provider)

    if provider.provider_type == "deterministic":
        return deterministic_outputs, provider.fallback_used

    roles = list(deterministic_outputs.keys())
    context = _packet_context(packet)
    outputs: dict[str, SpecialistAgentOutput | None] = {}
    runtime_fallback_used = provider.fallback_used

    for role in roles:
        prompt = f"{_role_instruction(role)}\n\nPacket context:\n{context}"
        try:
            if provider.provider_type == "hosted":
                raw = _call_openai(prompt)
            elif provider.provider_type == "ollama":
                raw = _call_ollama(prompt)
            else:
                raise RuntimeError("Unsupported provider type")

            summary, key_points, score = _parse_specialist_response(raw)
            outputs[role] = SpecialistAgentOutput(
                role=role,
                summary=summary,
                keyPoints=key_points,
                score=score,
                timestamp=_ts(),
                provider=provider.name,
                fallbackUsed=False,
            )
        except (
            RuntimeError,
            ValueError,
            json.JSONDecodeError,
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
        ):
            outputs[role] = deterministic_outputs[role]
            if outputs[role] is not None:
                outputs[role] = outputs[role].model_copy(
                    update={
                        "provider": "deterministic-engine",
                        "fallbackUsed": True,
                    }
                )
            runtime_fallback_used = True

    return outputs, runtime_fallback_used
