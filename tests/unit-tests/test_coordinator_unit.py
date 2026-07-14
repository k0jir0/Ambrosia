from __future__ import annotations

import urllib.error

import pytest

from services.api.app import coordinator
from services.api.app.providers import ProviderSelection


def _provider(provider_type: str = "deterministic", fallback_used: bool = False) -> ProviderSelection:
    return ProviderSelection(
        name=f"{provider_type}-unit",
        provider_type=provider_type,
        fallback_chain=[f"{provider_type}-unit", "deterministic-engine"],
        fallback_used=fallback_used,
        reason="unit test",
    )


def test_coordinator_score_helpers_are_bounded(packet_factory) -> None:
    uptrend = packet_factory()
    downtrend = packet_factory().model_copy(update={"technicals": packet_factory().technicals.model_copy(update={"trend": "downtrend", "rsi": 20})})
    no_context = packet_factory(include_market=False)

    assert coordinator._bounded_score(-1) == 0
    assert coordinator._bounded_score(101) == 100
    assert coordinator._trend_score(uptrend) > coordinator._trend_score(downtrend)
    assert coordinator._trend_score(no_context) == 50
    assert coordinator._sentiment_score(no_context) == 50


def test_parse_specialist_response_pads_points_and_clamps_score() -> None:
    summary, points, score = coordinator._parse_specialist_response(
        '{"summary":"Good","keyPoints":["one"],"score":125}'
    )

    assert summary == "Good"
    assert points == ["one", "No additional point", "No additional point"]
    assert score == 100


def test_packet_context_and_role_instruction_preserve_safety_contract(packet_factory) -> None:
    packet = packet_factory()

    context = coordinator._packet_context(packet)
    instruction = coordinator._role_instruction("risk")

    assert "ticker=SPY" in context
    assert "confidence=64" in context
    assert "riskStatus=monitoring" in context
    assert "Respond with strict JSON only" in instruction
    assert "Do not claim unavailable data" in instruction


def test_run_specialists_returns_all_deterministic_roles(packet_factory) -> None:
    outputs, fallback_used = coordinator.run_specialists(packet_factory(), _provider("deterministic"))

    assert fallback_used is False
    assert set(outputs) == {
        "marketData",
        "technical",
        "sentiment",
        "interMarket",
        "fundamental",
        "quant",
        "bull",
        "bear",
        "risk",
        "pmSynthesis",
    }
    assert outputs["pmSynthesis"].provider == "deterministic-unit"
    assert outputs["pmSynthesis"].fallbackUsed is False


def test_run_specialists_uses_hosted_json_when_provider_call_succeeds(monkeypatch, packet_factory) -> None:
    monkeypatch.setattr(
        coordinator,
        "_call_openai",
        lambda prompt: '{"summary":"Hosted summary","keyPoints":["a","b","c"],"score":77}',
    )

    outputs, fallback_used = coordinator.run_specialists(packet_factory(), _provider("hosted"))

    assert fallback_used is False
    assert outputs["risk"].summary == "Hosted summary"
    assert outputs["risk"].keyPoints == ["a", "b", "c"]
    assert outputs["risk"].score == 77
    assert outputs["risk"].fallbackUsed is False


def test_run_specialists_falls_back_per_role_when_provider_call_fails(monkeypatch, packet_factory) -> None:
    def fail(prompt: str) -> str:
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(coordinator, "_call_openai", fail)

    outputs, fallback_used = coordinator.run_specialists(packet_factory(), _provider("hosted"))

    assert fallback_used is True
    assert outputs["risk"].provider == "deterministic-engine"
    assert outputs["risk"].fallbackUsed is True


def test_parse_specialist_response_rejects_invalid_json() -> None:
    with pytest.raises(ValueError):
        coordinator._parse_specialist_response("not-json")
