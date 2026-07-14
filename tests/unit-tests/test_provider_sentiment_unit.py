from __future__ import annotations

import urllib.error

import pytest

from services.api.app import market_providers, providers, sentiment


def test_provider_resolution_prefers_explicit_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    selection = providers.resolve_provider("deterministic")

    assert selection.name == "deterministic-engine"
    assert selection.provider_type == "deterministic"
    assert selection.fallback_used is False
    assert selection.fallback_chain == ["deterministic-engine"]


def test_provider_resolution_falls_back_when_requested_provider_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    hosted = providers.resolve_provider("hosted")
    ollama = providers.resolve_provider("ollama")
    hybrid = providers.resolve_provider("hybrid")

    assert hosted.provider_type == "deterministic"
    assert hosted.fallback_used is True
    assert ollama.provider_type == "deterministic"
    assert ollama.fallback_used is True
    assert hybrid.provider_type == "deterministic"
    assert hybrid.fallback_chain == ["hosted-llm", "ollama-local", "deterministic-engine"]


def test_provider_resolution_detects_hosted_and_ollama_configuration(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "unit-test")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    hosted = providers.resolve_provider("hosted")
    ollama = providers.resolve_provider("ollama")
    hybrid = providers.resolve_provider("hybrid")
    status = providers.provider_status()

    assert hosted.provider_type == "hosted"
    assert ollama.provider_type == "ollama"
    assert hybrid.provider_type == "hosted"
    assert status == {"hostedConfigured": True, "ollamaConfigured": True}


def test_market_provider_status_uses_yahoo_without_polygon_key(monkeypatch) -> None:
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)

    provider = market_providers.resolve_market_provider()
    status = market_providers.market_provider_status()

    assert provider.provider_type == "yahoo"
    assert provider.fallback_chain == ["yahoo-finance", "deterministic"]
    assert status["polygonConfigured"] is False


def test_market_provider_status_uses_polygon_when_key_is_present(monkeypatch) -> None:
    monkeypatch.setenv("POLYGON_API_KEY", "unit-test")

    provider = market_providers.resolve_market_provider()

    assert provider.name == "polygon-io"
    assert provider.provider_type == "polygon"
    assert provider.fallback_chain == ["polygon-io", "yahoo-finance", "deterministic"]


def test_polygon_fetch_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("POLYGON_API_KEY", raising=False)

    with pytest.raises(ValueError, match="POLYGON_API_KEY"):
        market_providers.fetch_polygon_series("SPY")


def test_sentiment_word_scoring_and_classification_boundaries() -> None:
    assert sentiment._score_text("Strong growth and bullish upgrade") == 4
    assert sentiment._score_text("Weak loss risk and downgrade") == -4
    assert sentiment._classify_sentiment(60) == "bullish"
    assert sentiment._classify_sentiment(40) == "bearish"
    assert sentiment._classify_sentiment(50) == "neutral"
    assert sentiment._classify_trend(58) == "strengthening"
    assert sentiment._classify_trend(42) == "weakening"
    assert sentiment._classify_trend(50) == "stable"


def test_fallback_sentiment_is_deterministic_by_ticker() -> None:
    first = sentiment._fallback_sentiment("SPY")
    second = sentiment._fallback_sentiment("SPY")
    other = sentiment._fallback_sentiment("QQQ")

    assert first.overallScore == second.overallScore
    assert first.socialScore == second.socialScore
    assert first.overallScore != other.overallScore
    assert first.sourceConfidence == "demo"
    assert first.dataMode == "demo"


def test_build_sentiment_falls_back_when_rss_fetch_fails(monkeypatch) -> None:
    def fail_fetch(ticker: str):
        raise urllib.error.URLError("network blocked")

    monkeypatch.setattr(sentiment, "_fetch_rss_sentiment", fail_fetch)

    result = sentiment.build_sentiment("SPY")

    assert result.sources == ["Deterministic sentiment fallback"]
    assert result.sourceConfidence == "demo"
