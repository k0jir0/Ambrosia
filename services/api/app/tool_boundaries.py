from __future__ import annotations

from .models import ToolBoundary


def list_tool_boundaries() -> list[ToolBoundary]:
    # Internal boundaries are intentionally shaped to map 1:1 into MCP serverization later.
    return [
        ToolBoundary(
            name="Market_data_tools",
            description="Fetch market snapshots and instrument time-series with provenance labels",
            mode="mcp-compatible",
        ),
        ToolBoundary(
            name="Retrieval_tools",
            description="Query review/packet memory with source and confidence annotations",
            mode="mcp-compatible",
        ),
        ToolBoundary(
            name="Indicator_tools",
            description="Calculate RSI, MACD, moving averages, volatility, and trend state",
            mode="mcp-compatible",
        ),
        ToolBoundary(
            name="Sentiment_tools",
            description="Resolve sentiment from source adapters with deterministic fallback",
            mode="mcp-compatible",
        ),
        ToolBoundary(
            name="Backtest_tools",
            description="Prepare and run gated backtest flows for eligible packets",
            mode="internal",
        ),
        ToolBoundary(
            name="Report_tools",
            description="Generate packet exports for investor/demo narratives",
            mode="internal",
        ),
        ToolBoundary(
            name="Risk_tools",
            description="Monitor risk state and trigger follow-up guardrail events",
            mode="mcp-compatible",
        ),
    ]
