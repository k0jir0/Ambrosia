#!/usr/bin/env python3
"""
Phase C1: Discovery Layer - NYSE Scanner-Style Thesis Discovery
Signal discovery pipeline for candidate ideas with explicit provenance.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class Signal:
    """A single discovery signal"""
    signal_id: str
    signal_type: Literal["momentum", "value", "technical", "sentiment", "fundamental"]
    ticker: str
    confidence: float  # 0-100
    timeframe: str  # "1d", "1w", "1m"
    provenance: str  # Which data/analysis produced this
    recommendation: str  # "buy", "sell", "hold"
    details: dict


@dataclass
class Thesis:
    """A thesis seed generated from signals"""
    thesis_id: str
    created_at: str
    ticker: str
    title: str
    hypothesis: str
    supporting_signals: list[str]  # List of signal IDs
    confidence_score: float  # Aggregate confidence
    market_cap_range: str
    sector: str
    provenance: str  # How this thesis was discovered


class ThesisDiscoveryEngine:
    """Discovers thesis opportunities from market signals"""
    
    def __init__(self):
        self.signals: dict[str, Signal] = {}
        self.theses: dict[str, Thesis] = {}
    
    def add_signal(self, signal: Signal) -> None:
        """Add a discovery signal"""
        self.signals[signal.signal_id] = signal
    
    def generate_thesis_from_signals(self, signals: list[Signal], title: str, hypothesis: str) -> Thesis:
        """Generate a thesis from a set of signals"""
        thesis_id = f"thesis_{len(self.theses) + 1:04d}"
        avg_confidence = sum(s.confidence for s in signals) / len(signals) if signals else 50
        
        thesis = Thesis(
            thesis_id=thesis_id,
            created_at=datetime.now().isoformat(),
            ticker=signals[0].ticker if signals else "UNKNOWN",
            title=title,
            hypothesis=hypothesis,
            supporting_signals=[s.signal_id for s in signals],
            confidence_score=avg_confidence,
            market_cap_range="unknown",
            sector="unknown",
            provenance="signal_aggregation",
        )
        
        self.theses[thesis_id] = thesis
        return thesis
    
    def discover_theses_by_pattern(self) -> list[Thesis]:
        """Discover theses using pattern matching"""
        discovered = []
        
        # Group signals by ticker
        by_ticker = {}
        for signal in self.signals.values():
            if signal.ticker not in by_ticker:
                by_ticker[signal.ticker] = []
            by_ticker[signal.ticker].append(signal)
        
        # Pattern 1: Multiple bullish signals -> Buy thesis
        for ticker, signals_list in by_ticker.items():
            bullish_signals = [s for s in signals_list if s.recommendation == "buy"]
            if len(bullish_signals) >= 2:
                avg_conf = sum(s.confidence for s in bullish_signals) / len(bullish_signals)
                if avg_conf >= 70:
                    thesis = self.generate_thesis_from_signals(
                        bullish_signals,
                        title=f"{ticker}: Convergent Bullish Pattern",
                        hypothesis=f"Multiple bullish signals align for {ticker}, suggesting upside opportunity."
                    )
                    discovered.append(thesis)
        
        return discovered
    
    def to_dict(self) -> dict:
        """Convert to dict for serialization"""
        return {
            "timestamp": datetime.now().isoformat(),
            "signals_count": len(self.signals),
            "theses_count": len(self.theses),
            "signals": [asdict(s) for s in self.signals.values()],
            "theses": [asdict(t) for t in self.theses.values()],
        }


def create_sample_discovery_signals() -> list[Signal]:
    """Create sample market discovery signals"""
    return [
        Signal(
            signal_id="sig_0001",
            signal_type="momentum",
            ticker="NVDA",
            confidence=85,
            timeframe="1w",
            provenance="RSI reversal at oversold",
            recommendation="buy",
            details={"rsi": 28, "previous_low": 95.2},
        ),
        Signal(
            signal_id="sig_0002",
            signal_type="technical",
            ticker="NVDA",
            confidence=78,
            timeframe="1d",
            provenance="Golden cross: 50MA > 200MA",
            recommendation="buy",
            details={"ma50": 108.3, "ma200": 102.1},
        ),
        Signal(
            signal_id="sig_0003",
            signal_type="fundamental",
            ticker="NVDA",
            confidence=72,
            timeframe="1m",
            provenance="Earnings growth: 35% YoY",
            recommendation="buy",
            details={"eps_growth": 0.35, "pe_ratio": 42},
        ),
        Signal(
            signal_id="sig_0004",
            signal_type="sentiment",
            ticker="TSLA",
            confidence=65,
            timeframe="1w",
            provenance="Analyst upgrades trend",
            recommendation="buy",
            details={"upgrades_last_week": 3, "target_price": 285},
        ),
        Signal(
            signal_id="sig_0005",
            signal_type="value",
            ticker="SPY",
            confidence=55,
            timeframe="1m",
            provenance="VIX mean reversion play",
            recommendation="hold",
            details={"vix_level": 18, "historical_mean": 16},
        ),
    ]


if __name__ == "__main__":
    # Create discovery engine
    engine = ThesisDiscoveryEngine()
    
    # Add sample signals
    for signal in create_sample_discovery_signals():
        engine.add_signal(signal)
    
    # Discover theses
    discovered_theses = engine.discover_theses_by_pattern()
    
    # Save artifact
    artifact_path = Path("artifacts/discovery-theses.json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    
    output = engine.to_dict()
    with open(artifact_path, "w") as f:
        json.dump(output, f, indent=2)
    
    print("Discovery Engine - Thesis Generation Report")
    print("=" * 70)
    print(f"Total Signals Processed: {output['signals_count']}")
    print(f"Theses Generated: {output['theses_count']}")
    
    if discovered_theses:
        print(f"\nDiscovered Theses:")
        for thesis in discovered_theses:
            print(f"\n  {thesis.thesis_id}: {thesis.title}")
            print(f"  Ticker: {thesis.ticker}")
            print(f"  Confidence: {thesis.confidence_score:.1f}%")
            print(f"  Hypothesis: {thesis.hypothesis}")
            print(f"  Supporting Signals: {len(thesis.supporting_signals)}")
    
    print(f"\nTheses report saved to: {artifact_path}")
