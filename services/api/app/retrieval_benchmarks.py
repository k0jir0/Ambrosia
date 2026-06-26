"""
Retrieval Quality Benchmark Fixtures
Used by CI and evals to test retrieval quality consistency and drift detection.

These fixtures represent realistic retrieval scenarios and expected performance.
"""

from dataclasses import dataclass


@dataclass
class RetrievalBenchmarkCase:
    """Single benchmark test case"""
    name: str
    description: str
    query: str
    source_documents: list[tuple[str, str]]  # (id, text) pairs
    relevant_doc_ids: list[str]  # Ground truth relevant IDs
    expected_metrics: dict[str, float]  # expected precision@5, recall@5, etc.
    category: str  # "semantic", "keyword", "mixed"


# Realistic benchmark cases for investment decision retrieval
RETRIEVAL_BENCHMARKS = [
    RetrievalBenchmarkCase(
        name="tech_earnings_retrieval",
        description="User searches for prior tech earnings analysis related to NVDA",
        query="semiconductor earnings guidance NVIDIA",
        source_documents=[
            ("doc-1", "NVIDIA Q2 earnings guidance raised due to AI datacenter demand"),
            ("doc-2", "Semiconductor earnings cycle analysis 2026"),
            ("doc-3", "TSLA earnings miss on guidance, stock falls 3%"),
            ("doc-4", "Tech sector earnings season outlook for Q3"),
            ("doc-5", "INTC guidance disappoints, market rotates to NVDA"),
            ("doc-6", "Lithium earnings surprise downward, battery makers impacted"),
        ],
        relevant_doc_ids=["doc-1", "doc-2", "doc-4", "doc-5"],
        expected_metrics={
            "precision_at_5": 0.60,  # Baseline with keyword matching
            "recall_at_5": 0.75,  # Should catch most relevant docs in top 5
            "ndcg_at_5": 0.45,  # Simple keyword matching, not perfect ranking
            "mrr": 0.33,  # First relevant hit should appear reasonably soon
        },
        category="semantic",
    ),
    RetrievalBenchmarkCase(
        name="momentum_signal_retrieval",
        description="Search for previous momentum reversal patterns",
        query="momentum reversal mean reversion RSI oversold",
        source_documents=[
            ("doc-7", "RSI oversold reversal pattern identified in 3 of last 5 trades"),
            ("doc-8", "Momentum mean reversion strategy backtest results: 65% win rate"),
            ("doc-9", "Market technical analysis: support level holding"),
            ("doc-10", "Volatility spike often precedes momentum reversal"),
            ("doc-11", "Historical pattern: RSI < 30 has 60% accuracy for 2-week reversal"),
            ("doc-12", "Sentiment data shows extreme pessimism, contrarian signal"),
        ],
        relevant_doc_ids=["doc-7", "doc-8", "doc-10", "doc-11"],
        expected_metrics={
            "precision_at_5": 0.60,
            "recall_at_5": 0.75,
            "ndcg_at_5": 0.45,
            "mrr": 0.33,
        },
        category="semantic",
    ),
    RetrievalBenchmarkCase(
        name="risk_framework_retrieval",
        description="Find previous portfolio risk analysis for similar positions",
        query="concentration risk sector overlap risk budget",
        source_documents=[
            ("doc-13", "Portfolio concentration: 40% in semis, 20% in mega-cap tech"),
            ("doc-14", "Risk budget allocation: 2% per position, 8% sector max"),
            ("doc-15", "Correlation analysis: high overlap between tech holdings"),
            ("doc-16", "VaR model shows 15% tail risk in current allocation"),
            ("doc-17", "Market liquidity check: 5M share position absorbs 2bps slippage"),
            ("doc-18", "Sector rotation strategy to reduce concentration"),
        ],
        relevant_doc_ids=["doc-13", "doc-14", "doc-15", "doc-16"],
        expected_metrics={
            "precision_at_5": 0.60,
            "recall_at_5": 0.75,
            "ndcg_at_5": 0.45,
            "mrr": 0.33,
        },
        category="semantic",
    ),
    RetrievalBenchmarkCase(
        name="keyword_exact_match",
        description="Simple keyword search for specific ticker history",
        query="TSLA",
        source_documents=[
            ("doc-19", "TSLA Long; thesis: FSD progress accelerates adoption"),
            ("doc-20", "TSLA Sell; macro headwind: rate hikes slow EV demand"),
            ("doc-21", "Tesla supplier analysis: TSLA SEMI ramp"),
            ("doc-22", "Energy stocks: TSLA vs traditional energy winners"),
            ("doc-23", "Quarterly earnings: MSFT beats, TSLA mixed"),
            ("doc-24", "Lithium miners benefit from TSLA volume growth"),
        ],
        relevant_doc_ids=["doc-19", "doc-20", "doc-21", "doc-23"],
        expected_metrics={
            "precision_at_5": 0.60,  # Keyword matching baseline
            "recall_at_5": 0.75,
            "ndcg_at_5": 0.45,
            "mrr": 0.33,
        },
        category="keyword",
    ),
    RetrievalBenchmarkCase(
        name="mixed_query_style",
        description="User combines ticker, signal, and risk terms",
        query="SPY market sentiment overbought risk",
        source_documents=[
            ("doc-25", "SPY technicals: overbought RSI 75, VIX near lows"),
            ("doc-26", "Market sentiment survey: 85% bulls, extreme euphoria"),
            ("doc-27", "SPY support levels: 450, 440, 430"),
            ("doc-28", "Risk parity model: equities 60%, bonds 40%"),
            ("doc-29", "Historical: similar sentiment peaks preceded 5-15% corrections"),
            ("doc-30", "VIX options: skew suggests tail risk hedging"),
        ],
        relevant_doc_ids=["doc-25", "doc-26", "doc-29", "doc-30"],
        expected_metrics={
            "precision_at_5": 0.60,
            "recall_at_5": 0.75,
            "ndcg_at_5": 0.45,
            "mrr": 0.33,
        },
        category="mixed",
    ),
]


def get_benchmark_by_name(name: str) -> RetrievalBenchmarkCase | None:
    """Get a specific benchmark case by name"""
    for case in RETRIEVAL_BENCHMARKS:
        if case.name == name:
            return case
    return None


def get_benchmarks_by_category(category: str) -> list[RetrievalBenchmarkCase]:
    """Get all benchmarks for a specific category"""
    return [case for case in RETRIEVAL_BENCHMARKS if case.category == category]


def get_all_benchmarks() -> list[RetrievalBenchmarkCase]:
    """Get all benchmark cases"""
    return RETRIEVAL_BENCHMARKS.copy()
