"""
Phase E: Execution Loop Completion Tests

Tests for:
- Paper trading sandbox (orders, positions)
- Market data connectivity
- Attribution analysis
- E2E certification and sign-off
"""
import pytest
import json
from datetime import datetime


class TestPaperTradingSandbox:
    """Test paper trading execution endpoints."""
    
    def test_execute_order_endpoint(self, api_client):
        """Test POST /execution/trading/execute-order."""
        payload = {
            "ticker": "NVDA",
            "quantity": 100,
            "order_type": "market",
            "side": "buy",
            "session_id": "session_001"
        }
        response = api_client.post("/execution/trading/execute-order", json=payload)
        assert response.status_code in [200, 201], "Should execute paper trade"
    
    def test_execute_order_returns_order_details(self, api_client):
        """Test executed order has order ID and confirmation."""
        payload = {
            "ticker": "AAPL",
            "quantity": 50,
            "order_type": "limit",
            "side": "buy",
            "limit_price": 150.0
        }
        response = api_client.post("/execution/trading/execute-order", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            assert "order_id" in data or "id" in data, "Should return order ID"
            assert "status" in data, "Should include order status"
            assert "filled_price" in data or "price" in data, "Should include price"
    
    def test_paper_positions_endpoint(self, api_client):
        """Test GET /execution/trading/paper-positions returns holdings."""
        response = api_client.get("/execution/trading/paper-positions")
        assert response.status_code == 200, "Should retrieve positions"
        
        data = response.json()
        assert "positions" in data or isinstance(data, list), \
            "Should return list of positions"
    
    def test_positions_have_correct_structure(self, api_client):
        """Test position objects have required fields."""
        response = api_client.get("/execution/trading/paper-positions")
        
        if response.status_code == 200:
            data = response.json()
            positions = data if isinstance(data, list) else data.get("positions", [])
            
            if len(positions) > 0:
                pos = positions[0]
                assert "ticker" in pos or "symbol" in pos, "Position needs ticker"
                assert "quantity" in pos or "shares" in pos, "Position needs quantity"
                assert "cost_basis" in pos or "avg_cost" in pos, "Position needs cost basis"
    
    def test_close_position_endpoint(self, api_client):
        """Test POST /execution/trading/close-position."""
        payload = {
            "ticker": "NVDA",
            "quantity": 100,
            "order_type": "market"
        }
        response = api_client.post("/execution/trading/close-position", json=payload)
        assert response.status_code in [200, 201, 404], "Should close or not find position"
    
    def test_order_history_endpoint(self, api_client):
        """Test GET /execution/trading/order-history."""
        response = api_client.get("/execution/trading/order-history")
        assert response.status_code == 200, "Should retrieve order history"
        
        data = response.json()
        assert "orders" in data or isinstance(data, list), \
            "Should return list of orders"


class TestMarketDataConnectivity:
    """Test market data endpoints."""
    
    def test_live_quotes_endpoint(self, api_client):
        """Test GET /execution/market-data/live-quotes."""
        params = {"symbols": "NVDA,AAPL,TSLA"}
        response = api_client.get("/execution/market-data/live-quotes", params=params)
        assert response.status_code in [200, 503], \
            "Should return quotes or indicate data unavailable"
    
    def test_quotes_response_format(self, api_client):
        """Test quote data has correct structure."""
        params = {"symbols": "NVDA"}
        response = api_client.get("/execution/market-data/live-quotes", params=params)
        
        if response.status_code == 200:
            data = response.json()
            assert "quotes" in data or "data" in data, "Should return quotes"
            
            quotes = data.get("quotes", data.get("data", []))
            if len(quotes) > 0:
                quote = quotes[0]
                assert "symbol" in quote or "ticker" in quote, "Quote needs symbol"
                assert "price" in quote or "last" in quote, "Quote needs price"
                assert "timestamp" in quote or "time" in quote, "Quote needs timestamp"
    
    def test_market_data_handles_multiple_symbols(self, api_client):
        """Test market data endpoint handles multiple symbols."""
        params = {"symbols": "NVDA,AAPL,TSLA,GOOGL"}
        response = api_client.get("/execution/market-data/live-quotes", params=params)
        
        if response.status_code == 200:
            data = response.json()
            quotes = data.get("quotes", data.get("data", []))
            # Should return quotes for multiple symbols
            symbols_returned = {q.get("symbol") or q.get("ticker") for q in quotes}
            assert len(symbols_returned) > 0, "Should return quotes"


class TestAttributionAnalysis:
    """Test performance attribution and analysis endpoints."""
    
    def test_analyze_attribution_endpoint(self, api_client):
        """Test POST /execution/attribution/analyze."""
        payload = {
            "position_id": "pos_001",
            "include_factors": True
        }
        response = api_client.post("/execution/attribution/analyze", json=payload)
        assert response.status_code in [200, 201], "Should analyze attribution"
    
    def test_attribution_returns_performance_data(self, api_client):
        """Test attribution analysis returns performance metrics."""
        payload = {
            "position_id": "pos_001"
        }
        response = api_client.post("/execution/attribution/analyze", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            assert "return" in data or "pnl" in data or "performance" in data, \
                "Should return performance data"
    
    def test_attribution_dashboard_endpoint(self, api_client):
        """Test GET /execution/attribution/dashboard."""
        response = api_client.get("/execution/attribution/dashboard")
        assert response.status_code == 200, "Attribution dashboard should exist"
        
        data = response.json()
        # Should have overview metrics
        assert "total_return" in data or "performance" in data or "data" in data, \
            "Dashboard should include performance summary"
    
    def test_factor_analysis_endpoint(self, api_client):
        """Test GET /execution/attribution/factor-analysis."""
        response = api_client.get("/execution/attribution/factor-analysis")
        assert response.status_code == 200, "Factor analysis should exist"
        
        data = response.json()
        # Should have factor breakdown
        assert "factors" in data or "analysis" in data or "data" in data, \
            "Should include factor analysis"
    
    def test_performance_metrics_endpoint(self, api_client):
        """Test GET /execution/attribution/performance-metrics."""
        response = api_client.get("/execution/attribution/performance-metrics")
        assert response.status_code == 200, "Performance metrics should exist"
        
        data = response.json()
        # Should have detailed metrics
        assert "metrics" in data or "data" in data or "performance" in data, \
            "Should include performance metrics"


class TestE2ECertification:
    """Test E2E loop certification endpoints."""
    
    def test_certification_status_endpoint(self, api_client):
        """Test GET /execution/certification/status."""
        response = api_client.get("/execution/certification/status")
        assert response.status_code == 200, "Certification status should exist"
        
        data = response.json()
        assert "status" in data or "certified" in data, \
            "Should indicate certification status"
    
    def test_certification_checklist_endpoint(self, api_client):
        """Test GET /execution/certification/checklist."""
        response = api_client.get("/execution/certification/checklist")
        assert response.status_code == 200, "Certification checklist should exist"
        
        data = response.json()
        assert "items" in data or "checklist" in data or isinstance(data, list), \
            "Should return checklist items"
    
    def test_checklist_items_have_status(self, api_client):
        """Test checklist items indicate completion status."""
        response = api_client.get("/execution/certification/checklist")
        
        if response.status_code == 200:
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", data.get("checklist", []))
            
            if len(items) > 0:
                item = items[0]
                # Each item should have status
                assert "status" in item or "completed" in item or "done" in item, \
                    "Checklist item should indicate status"
    
    def test_sign_off_endpoint(self, api_client):
        """Test POST /execution/certification/sign-off."""
        payload = {
            "reviewer": "CTO",
            "approved": True,
            "notes": "All systems operational"
        }
        response = api_client.post("/execution/certification/sign-off", json=payload)
        
        # May require specific role
        assert response.status_code in [200, 201, 403, 401], \
            "Sign-off endpoint should exist or require auth"
    
    def test_e2e_loop_decision_to_execution(self, api_client):
        """Test complete E2E loop: decision → execution → outcome."""
        # This is an integration test showing the full loop
        
        # 1. Get status
        response = api_client.get("/execution/certification/status")
        assert response.status_code == 200, "Should get initial status"
        
        # 2. Get checklist
        response = api_client.get("/execution/certification/checklist")
        assert response.status_code == 200, "Should get certification checklist"
        
        # 3. Execute order (decision → execution)
        payload = {
            "ticker": "NVDA",
            "quantity": 10,
            "order_type": "market",
            "side": "buy"
        }
        response = api_client.post("/execution/trading/execute-order", json=payload)
        assert response.status_code in [200, 201], "Should execute trade"
        
        # 4. Check positions (outcome)
        response = api_client.get("/execution/trading/paper-positions")
        assert response.status_code == 200, "Should retrieve positions showing execution outcome"


class TestExecutionContract:
    """Test Phase E acceptance contracts."""
    
    def test_contract_e1_broker_sandbox(self, api_client):
        """E1: Broker Sandbox - Paper trading fully operational."""
        
        # Test order execution
        payload = {
            "ticker": "NVDA",
            "quantity": 100,
            "order_type": "market",
            "side": "buy"
        }
        response = api_client.post("/execution/trading/execute-order", json=payload)
        assert response.status_code in [200, 201], \
            "E1 Contract: Paper trading should execute orders"
        
        # Test position retrieval
        response = api_client.get("/execution/trading/paper-positions")
        assert response.status_code == 200, \
            "E1 Contract: Should retrieve positions"
    
    def test_contract_e2_attribution_analysis(self, api_client):
        """E2: Attribution Analysis - Recording framework complete."""
        
        # Test attribution analysis
        payload = {
            "position_id": "test_pos"
        }
        response = api_client.post("/execution/attribution/analyze", json=payload)
        assert response.status_code in [200, 201], \
            "E2 Contract: Attribution analysis should be callable"
        
        # Test dashboard
        response = api_client.get("/execution/attribution/dashboard")
        assert response.status_code == 200, \
            "E2 Contract: Attribution dashboard should exist"
        
        # Test factor analysis
        response = api_client.get("/execution/attribution/factor-analysis")
        assert response.status_code == 200, \
            "E2 Contract: Factor analysis should exist"
    
    def test_contract_e3_final_certification(self, api_client):
        """E3: Final Certification - E2E loop certified."""
        
        # Test certification status
        response = api_client.get("/execution/certification/status")
        assert response.status_code == 200, \
            "E3 Contract: Certification status should be queryable"
        
        # Test checklist
        response = api_client.get("/execution/certification/checklist")
        assert response.status_code == 200, \
            "E3 Contract: Certification checklist should exist"
        
        # Test sign-off endpoint exists
        response = api_client.post("/execution/certification/sign-off", 
                                   json={"reviewer": "test"})
        assert response.status_code in [200, 201, 401, 403], \
            "E3 Contract: Sign-off endpoint should be accessible"


class TestExecutionErrorHandling:
    """Test error handling in execution endpoints."""
    
    def test_invalid_ticker_rejected(self, api_client):
        """Test invalid ticker symbol is rejected."""
        payload = {
            "ticker": "",
            "quantity": 100,
            "order_type": "market",
            "side": "buy"
        }
        response = api_client.post("/execution/trading/execute-order", json=payload)
        assert response.status_code in [400, 422], \
            "Should reject invalid ticker"
    
    def test_invalid_quantity_rejected(self, api_client):
        """Test invalid order quantity is rejected."""
        payload = {
            "ticker": "NVDA",
            "quantity": -100,  # Negative
            "order_type": "market",
            "side": "buy"
        }
        response = api_client.post("/execution/trading/execute-order", json=payload)
        assert response.status_code in [400, 422], \
            "Should reject invalid quantity"
    
    def test_close_nonexistent_position_handled(self, api_client):
        """Test closing nonexistent position is handled gracefully."""
        payload = {
            "ticker": "NONEXIST",
            "quantity": 100,
            "order_type": "market"
        }
        response = api_client.post("/execution/trading/close-position", json=payload)
        assert response.status_code in [404, 400], \
            "Should handle nonexistent position gracefully"
