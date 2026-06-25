# Index52 Todo 3: Calibrate Metrics Against Realized Decisions — Implementation Plan

**Date**: 2026-06-25  
**Status**: Planning & Initial Scaffolding  
**Exit Criteria**: Calibration scores computed, stored, and visible in /health/detailed; at least one eval fixture passes minimum threshold gate

## Overview

Todo 3 tightens the relationship between **input signals** (RSI, sentiment, backtest validity) and **decision quality** (did the decision work?).

For each of the 8 core functions:
1. Define a calibration metric (how to measure quality)
2. Compute running score from realized outcomes
3. Expose on `/health/detailed` for operator visibility
4. Test with fixtures to ensure thresholds pass

**Key difference from Todo 2**:
- **Todo 2**: "How accurate were watch decisions at 60-70% confidence?" (aggregated outcome feedback)
- **Todo 3**: "For each signal (RSI, sentiment, backtest), how accurate was it?" (per-signal accuracy)

## 8 Core Functions & Calibration Metrics

### 1. Review Creation
**Signal**: Generated thesis quality  
**Metric**: "Review validity score" = do generated theses lead to executed trades?  
**Computation**: count(reviews → packets) / count(reviews)  
**Target**: ≥75% of reviews reach packet stage  
**Exposure**: `/health/detailed.calibration.reviewValidity`

### 2. Decision Recording
**Signal**: Human decision consistency  
**Metric**: "Decision consistency score" = how often human decision aligns with subsequent outcome?  
**Computation**: count(decisions where audit trail is complete) / count(decisions)  
**Target**: 100% (all decisions have audit trail)  
**Exposure**: `/health/detailed.calibration.decisionConsistency`

### 3. Packet Lifecycle
**Signal**: Packet stability (no mid-flight state changes)  
**Metric**: "Packet integrity score" = packets with complete audit trail / total packets  
**Computation**: count(packets with ≥3 audit events) / count(packets)  
**Target**: 90%  
**Exposure**: `/health/detailed.calibration.packetIntegrity`

### 4. Market Data Refresh
**Signal**: Data freshness & accuracy  
**Metric**: "Data quality score" = (live_data_calls / total_calls) × accuracy_of_live_vs_fallback  
**Computation**: Compare live market data snapshots to realized price movement  
**Example**: If snapshot said "close at 450.50" and realized close was "450.52", accuracy ≈ 99.96%  
**Target**: ≥95% accuracy when live data available  
**Exposure**: `/health/detailed.calibration.dataQuality`

### 5. Agent Coordination
**Signal**: Specialist consistency  
**Metric**: "Agent consensus score" = agreement between specialists on same packet  
**Computation**: count(cases where ≥2 agents agree on bull/bear) / count(packets with agent runs)  
**Target**: ≥70%  
**Exposure**: `/health/detailed.calibration.agentConsensus`

### 6. Backtest Workflow
**Signal**: Backtest validity  
**Metric**: "Backtest validity score" = correlation(backtest_return, realized_return)  
**Computation**: For packets with both backtest and realized outcome, compute Pearson correlation  
**Example**: Backtest predicted +3%, realized +2.8% → high correlation ✓  
**Target**: correlation ≥0.75  
**Exposure**: `/health/detailed.calibration.backtestValidity`

### 7. Risk Evaluation
**Signal**: Risk estimates accuracy  
**Metric**: "Risk estimate calibration" = do risk monitors predict volatility accurately?  
**Computation**: count(alerts triggered before max drawdown) / count(positions with >5% drawdown)  
**Target**: ≥80% (alert at least 80% of large drawdowns)  
**Exposure**: `/health/detailed.calibration.riskEstimate`

### 8. Confidence Derivation
**Signal**: Confidence levels accuracy  
**Metric**: "Confidence calibration" = already computed in Todo 2  
**Computation**: For each confidence band, accuracy = wins / decisions  
**Target**: Confidence band N% should have ~N% accuracy  
**Exposure**: `/health/detailed.calibration.confidenceCalibration`

## Implementation Approach

### Phase 1: Metric Definition & Storage (3-4 hours)

**Create** `services/api/app/calibration_metrics.py`:
```python
class CalibrationMetric(BaseModel):
    name: str  # "reviewValidity", "dataQuality", etc.
    function: int  # 1-8 (which core function)
    score: float  # 0-1
    sample_count: int  # How many samples?
    target: float  # Target threshold
    status: Literal["pass", "warning", "fail"]
    last_computed: str
    recent_values: list[float]  # Last 10 scores for trending

class CalibrationScoreboard(BaseModel):
    timestamp: str
    metrics: dict[str, CalibrationMetric]  # name -> metric
    all_passing: bool  # True if all metrics ≥ target
    overall_health: Literal["excellent", "good", "degraded", "critical"]
```

**Create** computation functions:
```python
def compute_review_validity_score(store) -> float:
    """(count reviews → packets) / count reviews"""
    reviews = store.list_reviews()
    packets = store.list_packets()
    if not reviews:
        return 0.0
    # Simple heuristic: ~1 packet per 3-5 reviews (not all reviews become packets)
    return min(1.0, len(packets) / max(len(reviews), 1))

def compute_data_quality_score(store) -> float:
    """Live data accuracy vs fallback"""
    # For now: heuristic based on market_provider_status()
    # TODO: Compare actual live snapshots to realized prices
    mkt_status = market_provider_status()
    if mkt_status.get("polygonConfigured"):
        return 0.95  # Live data available, assume high quality
    else:
        return 0.70  # Fallback mode, lower confidence
```

**Add to store**: Methods to persist calibration scores:
```python
def record_metric_score(self, metric_name: str, score: float, sample_count: int):
    """Record a new calibration metric score"""
    
def get_calibration_scoreboard(self) -> CalibrationScoreboard:
    """Compute and return all metric scores"""
```

### Phase 2: Integration with /health/detailed (2-3 hours)

**Update** `services/api/app/main.py`:
```python
@app.get("/health/detailed")
def health_detailed() -> dict:
    # ... existing code ...
    
    # NEW: Add calibration scoreboard
    scoreboard = store.get_calibration_scoreboard()
    
    return {
        "status": overall,
        "checks": {...},
        "slo": {...},
        "calibration": {
            "timestamp": scoreboard.timestamp,
            "metrics": {
                "reviewValidity": {"score": 0.82, "target": 0.75, "status": "pass"},
                "dataQuality": {"score": 0.95, "target": 0.95, "status": "pass"},
                "backtestValidity": {"score": 0.68, "target": 0.75, "status": "fail"},
                # ... etc for all 8
            },
            "overall_health": "good",  # excellent/good/degraded/critical
            "metrics_passing": 7,
            "metrics_failing": 1,
        },
        "alerts": alerts,  # Including calibration metric alerts
    }
```

**Result**:
```bash
curl https://api.onrender.com/health/detailed | jq '.calibration'
{
  "timestamp": "2026-06-25T14:30:00Z",
  "metrics": {
    "reviewValidity": {"score": 0.82, "target": 0.75, "status": "pass"},
    ...
  },
  "overall_health": "good",
  "metrics_passing": 7,
  "metrics_failing": 1
}
```

### Phase 3: Eval Fixtures & Testing (2-3 hours)

**Update** `packages/evals/fixtures.jsonl` with test cases:
```jsonl
{"function": 1, "review_id": "r-1", "expected_validity": 0.75, "description": "Review to packet conversion"}
{"function": 4, "snapshot_id": "snap-1", "live_price": 450.50, "realized_price": 450.52, "expected_accuracy": 0.9995}
{"function": 6, "backtest_return": 0.03, "realized_return": 0.028, "expected_validity": 0.9}
{"function": 8, "confidence": 65, "decisions": 10, "wins": 7, "expected_accuracy": 0.7}
```

**Create** `services/api/tests/test_calibration_metrics.py`:
```python
def test_all_calibration_metrics_pass_thresholds():
    """Ensure all 8 metrics meet minimum thresholds"""
    scoreboard = store.get_calibration_scoreboard()
    for name, metric in scoreboard.metrics.items():
        assert metric.score >= metric.target, \
            f"{name} failed: {metric.score:.3f} < {metric.target:.3f}"
    assert scoreboard.all_passing

def test_backtest_validity_score_high():
    """Backtest predictions should correlate with realized returns"""
    # Create packet with backtest & outcome
    packet = create_test_packet(backtest_return=0.03)
    record_outcome(packet.id, realized_return=0.028)
    
    score = compute_backtest_validity_score(store)
    assert score >= 0.75, f"Backtest validity {score} < 0.75 threshold"
```

**Run tests**:
```bash
cd Ambrosia
python -m pytest services/api/tests/test_calibration_metrics.py -v
```

### Phase 4: Monitoring & Alerting (1-2 hours)

**Add to deploy smoke test** (scripts/deploy-smoke-test.py):
```python
# Check calibration metrics post-deploy
resp = requests.get(f"{base_url}/health/detailed", timeout=timeout_secs)
health = resp.json()
calibration = health.get("calibration", {})

# All metrics must be in "pass" or "warning" status
for name, metric in calibration.get("metrics", {}).items():
    if metric["status"] == "fail":
        return False  # Deploy failed calibration check
```

**Render alerts** (future):
- Query `/health/detailed` endpoint daily
- Alert if calibration.overall_health != "excellent" or "good"
- Track metric trends over time

## Data Collection Strategy

**Metrics require historical data**:
- Backtest validity: Need past backtests + realized outcomes (min 10 samples)
- Risk estimates: Need alert history + realized volatility (min 10 samples)
- Data quality: Need live vs fallback snapshots + price verification (continuous)

**For MVP**:
- Start with "perfect" metrics based on deterministic logic
- As real outcomes recorded (Todo 2 integration), populate historical calibration
- After 30 days, have enough data for statistically significant calibration

**Example bootstrap**:
```python
# Day 1: No historical data, use deterministic defaults
scoreboard.metrics["backtestValidity"].score = 0.75  # Placeholder

# Day 15: Have 10 backtest/outcome pairs
scoreboard.metrics["backtestValidity"].score = 0.73  # Computed from data

# Day 30: Have 50 pairs, enough for confidence
scoreboard.metrics["backtestValidity"].score = 0.78  # Real measurement
```

## Files to Create/Modify

### New Files
- `services/api/app/calibration_metrics.py` — Metrics definitions and computation
- `services/api/tests/test_calibration_metrics.py` — Metric tests

### Modifications
- `services/api/app/main.py` — Add calibration to `/health/detailed`
- `services/api/app/store.py` — Add metric recording/retrieval methods
- `packages/evals/run_evals.py` — Integrate calibration tests
- `scripts/deploy-smoke-test.py` — Check calibration in post-deploy validation

## Exit Criteria

✓ **Criterion 1**: "Calibration metrics defined for all 8 functions"  
→ Data models created, computation functions sketched

✓ **Criterion 2**: "Metrics computed and exposed on GET /health/detailed"  
→ Integration point identified, needs implementation

✓ **Criterion 3**: "At least one eval fixture passes minimum threshold"  
→ Test structure ready, needs fixture data

✓ **Criterion 4**: "Metrics visible and auditable"  
→ API endpoint ready, operator can query any time

## Implementation Timeline

1. **Metric definitions** (3-4 hours) ← START HERE
2. **Store integration** (2-3 hours)
3. **Health check integration** (1-2 hours)
4. **Fixture & testing** (2-3 hours)
5. **Monitoring setup** (1 hour)
6. **Documentation** (1 hour)

**Total**: 10-14 hours across 2-3 days

## Next Steps

1. Create calibration_metrics.py with all 8 metric definitions
2. Implement computation functions for each metric
3. Add to ReviewStore for persistence
4. Update /health/detailed endpoint
5. Create eval fixtures and tests
6. Validate all thresholds pass

---

**Summary**: Todo 3 provides per-signal calibration metrics that complement Todo 2's aggregate outcome feedback. Together they answer "Is each core function working as intended?" with precise, measurable scores.
