#!/usr/bin/env python3
"""
Phase E: Execution Loop Completion
Broker sandbox integration with paper trading and attribution.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class PaperOrder:
    """Simulated (paper) order"""
    order_id: str
    ticker: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    created_at: str
    status: Literal["pending", "filled", "cancelled"]
    execution_price: float = 0.0


@dataclass
class Position:
    """Paper trading position"""
    position_id: str
    ticker: str
    quantity: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float


@dataclass
class ExecutionAttribution:
    """Attribution of trade outcome to factors"""
    execution_id: str
    ticker: str
    entry_thesis: str
    factors: list[str]
    outcome: str
    pnl_realized: float
    pnl_pct: float
    holding_period_days: int


class BrokerSandbox:
    """Sandbox environment for paper trading"""
    
    def __init__(self, initial_cash: float = 1000000.0):
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.orders: dict[str, PaperOrder] = {}
        self.executions: list[ExecutionAttribution] = []
        self.portfolio_value = initial_cash
    
    def place_order(self, ticker: str, side: Literal["buy", "sell"],
                    quantity: float, price: float) -> PaperOrder:
        """Place a paper trade order"""
        order_id = f"ord_{len(self.orders) + 1:06d}"
        order = PaperOrder(
            order_id=order_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=price,
            created_at=datetime.now().isoformat(),
            status="filled",
            execution_price=price,
        )
        
        self.orders[order_id] = order
        
        # Execute immediately in sandbox
        self._execute_order(order)
        
        return order
    
    def _execute_order(self, order: PaperOrder) -> None:
        """Execute a paper order"""
        if order.side == "buy":
            cost = order.quantity * order.execution_price
            if cost > self.cash:
                return  # Insufficient cash
            
            self.cash -= cost
            
            if order.ticker not in self.positions:
                self.positions[order.ticker] = Position(
                    position_id=f"pos_{order.ticker}",
                    ticker=order.ticker,
                    quantity=0,
                    avg_entry_price=0,
                    current_price=order.execution_price,
                    unrealized_pnl=0,
                    realized_pnl=0,
                )
            
            pos = self.positions[order.ticker]
            total_cost = pos.quantity * pos.avg_entry_price + order.quantity * order.execution_price
            pos.quantity += order.quantity
            pos.avg_entry_price = total_cost / pos.quantity if pos.quantity > 0 else 0
            pos.current_price = order.execution_price
        
        elif order.side == "sell":
            if order.ticker in self.positions:
                pos = self.positions[order.ticker]
                if pos.quantity >= order.quantity:
                    proceeds = order.quantity * order.execution_price
                    self.cash += proceeds
                    realized = proceeds - (order.quantity * pos.avg_entry_price)
                    pos.realized_pnl += realized
                    pos.quantity -= order.quantity
    
    def record_attribution(self, ticker: str, entry_thesis: str,
                          factors: list[str], outcome: str, pnl_pct: float) -> ExecutionAttribution:
        """Record attribution for a trade outcome"""
        attribution = ExecutionAttribution(
            execution_id=f"attr_{len(self.executions) + 1:06d}",
            ticker=ticker,
            entry_thesis=entry_thesis,
            factors=factors,
            outcome=outcome,
            pnl_realized=pnl_pct,
            pnl_pct=pnl_pct,
            holding_period_days=0,
        )
        
        self.executions.append(attribution)
        return attribution
    
    def get_portfolio_snapshot(self) -> dict:
        """Get current portfolio state"""
        total_market_value = self.cash + sum(
            p.quantity * p.current_price for p in self.positions.values()
        )
        total_unrealized = sum(
            (p.current_price - p.avg_entry_price) * p.quantity
            for p in self.positions.values()
        )
        total_realized = sum(p.realized_pnl for p in self.positions.values())
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cash_available": self.cash,
            "total_positions": len(self.positions),
            "total_market_value": total_market_value,
            "total_unrealized_pnl": total_unrealized,
            "total_realized_pnl": total_realized,
            "return_pct": ((total_market_value - 1000000) / 1000000 * 100),
            "positions": [asdict(p) for p in self.positions.values()],
        }
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        return {
            "timestamp": datetime.now().isoformat(),
            "total_orders": len(self.orders),
            "total_executions": len(self.executions),
            "portfolio_snapshot": self.get_portfolio_snapshot(),
            "execution_attributions": [asdict(a) for a in self.executions],
        }


def generate_execution_loop_demo() -> dict:
    """Generate demo of execution loop"""
    sandbox = BrokerSandbox(initial_cash=1000000.0)
    
    # Simulate a complete execution loop
    
    # Step 1: Place buy order based on thesis
    sandbox.place_order("NVDA", "buy", 1000, 108.50)
    
    # Step 2: Record attribution factors
    sandbox.record_attribution(
        ticker="NVDA",
        entry_thesis="Convergent bullish signals",
        factors=["RSI reversal", "Golden cross", "Earnings growth"],
        outcome="position_opened",
        pnl_pct=0.0,
    )
    
    # Step 3: Simulate price movement
    if "NVDA" in sandbox.positions:
        sandbox.positions["NVDA"].current_price = 112.30
    
    # Step 4: Close position
    sandbox.place_order("NVDA", "sell", 1000, 112.30)
    
    # Step 5: Record outcome attribution
    pnl_pct = ((112.30 - 108.50) / 108.50) * 100
    
    sandbox.record_attribution(
        ticker="NVDA",
        entry_thesis="Convergent bullish signals",
        factors=["RSI reversal", "Golden cross", "Earnings growth"],
        outcome="position_closed_profitable",
        pnl_pct=pnl_pct,
    )
    
    # Additional sample trades
    sandbox.place_order("TSLA", "buy", 500, 245.00)
    sandbox.record_attribution(
        ticker="TSLA",
        entry_thesis="Analyst upgrade trend",
        factors=["Upgrades", "Sentiment"],
        outcome="position_opened",
        pnl_pct=0.0,
    )
    
    return sandbox.to_dict()


if __name__ == "__main__":
    # Generate execution loop demo
    execution_data = generate_execution_loop_demo()
    
    # Save artifact
    artifact_path = Path("artifacts/execution-loop-demo.json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(artifact_path, "w") as f:
        json.dump(execution_data, f, indent=2)
    
    portfolio = execution_data["portfolio_snapshot"]
    
    print("Execution Loop - Broker Sandbox Demo")
    print("=" * 70)
    print(f"Total Orders: {execution_data['total_orders']}")
    print(f"Total Executions: {execution_data['total_executions']}")
    
    print("\nPortfolio Status:")
    print(f"  Cash: ${portfolio['cash_available']:,.2f}")
    print(f"  Market Value: ${portfolio['total_market_value']:,.2f}")
    print(f"  Total P&L: ${portfolio['total_realized_pnl'] + portfolio['total_unrealized_pnl']:,.2f}")
    print(f"  Return: {portfolio['return_pct']:.2f}%")
    
    if portfolio["positions"]:
        print("\nOpen Positions:")
        for pos in portfolio["positions"]:
            print(f"  {pos['ticker']}: {pos['quantity']} @ avg ${pos['avg_entry_price']:.2f}")
    
    if execution_data["execution_attributions"]:
        print("\nExecution Attribution:")
        for attr in execution_data["execution_attributions"]:
            print(f"  {attr['execution_id']}: {attr['ticker']} - {attr['outcome']}")
    
    print(f"\nExecution loop demo saved to: {artifact_path}")
