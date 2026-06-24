from __future__ import annotations

import random
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from .models import SentimentData

POSITIVE_WORDS = {
    "beat",
    "upgrade",
    "surge",
    "bullish",
    "gain",
    "rally",
    "strong",
    "growth",
    "optimism",
    "outperform",
}

NEGATIVE_WORDS = {
    "miss",
    "downgrade",
    "drop",
    "bearish",
    "loss",
    "selloff",
    "weak",
    "slowdown",
    "risk",
    "underperform",
}


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _score_text(text: str) -> int:
    words = {word.strip(".,:;!?()[]{}\"'`").lower() for word in text.split()}
    pos = len(words & POSITIVE_WORDS)
    neg = len(words & NEGATIVE_WORDS)
    return pos - neg


def _classify_sentiment(score: float) -> str:
    if score >= 60:
        return "bullish"
    if score <= 40:
        return "bearish"
    return "neutral"


def _classify_trend(score: float) -> str:
    if score >= 58:
        return "strengthening"
    if score <= 42:
        return "weakening"
    return "stable"


def _fetch_rss_sentiment(ticker: str) -> SentimentData:
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    request = urllib.request.Request(url, headers={"User-Agent": "Ambrosia/1.0"})

    with urllib.request.urlopen(request, timeout=4) as response:
        payload = response.read().decode("utf-8", errors="ignore")

    root = ET.fromstring(payload)
    items = root.findall("./channel/item")
    titles = [item.findtext("title", default="") for item in items[:20]]

    if not titles:
        raise ValueError("No RSS headlines available")

    scores = [_score_text(title) for title in titles]
    average = sum(scores) / len(scores)

    # Convert average score to 0-100 range around neutral midpoint 50.
    normalized = max(0.0, min(100.0, 50 + (average * 12)))

    return SentimentData(
        overallScore=round(normalized, 2),
        sentiment=_classify_sentiment(normalized),
        newsScore=round(normalized, 2),
        socialScore=None,
        trendDirection=_classify_trend(normalized),
        sources=["Yahoo Finance RSS"],
        lastUpdated=_timestamp(),
        sourceConfidence="verified",
    )


def _fallback_sentiment(ticker: str) -> SentimentData:
    seeded = random.Random(f"sentiment-{ticker.lower()}")
    score = 50 + seeded.uniform(-12, 12)

    return SentimentData(
        overallScore=round(score, 2),
        sentiment=_classify_sentiment(score),
        newsScore=round(score, 2),
        socialScore=round(50 + seeded.uniform(-10, 10), 2),
        trendDirection=_classify_trend(score),
        sources=["Deterministic sentiment fallback"],
        lastUpdated=_timestamp(),
        sourceConfidence="demo",
    )


def build_sentiment(ticker: str) -> SentimentData:
    try:
        return _fetch_rss_sentiment(ticker)
    except (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError):
        return _fallback_sentiment(ticker)
