# Todo 3: Calibration Metrics - Implementation Start

**Status**: 📋 **READY TO IMPLEMENT** (detailed plan exists)  
**Estimated Timeline**: 10-14 hours  
**Target Completion**: End of this session  

---

## Overview

Implement 8 calibration metrics that measure decision quality across the 8 core functions. These metrics feed into the operational scorecard (Todo 4) and enable Index39 certification.

**Exit Criteria**: All 8 metrics computed, recorded, and exposed via updated `/health/detailed` endpoint with calibration section showing metrics + targets + performance status.

---

## 8 Metrics to Implement

### 1. Review Validity (Target: 75%)

**What It Measures**: How often review recommendations are actually followed by packets.

**Computation**:
```
Reviews generated: 100
Packets created from reviews: 75
Review validity = 75 / 100 = 75%
```

**Data Source**:
- `store.list_reviews()` — get all reviews
- `store.list_packets()` — filter to packets created from reviews (check audit trail)
- Link via `packet.audit[].eventType == "review.converted_to_packet"`

**Storage**:
```python
class ReviewValidityMetric:
    total_reviews: int
    reviews_converted: int
    conversion_rate: float  # target: 0.75
    status: "ok" | "low"  # ok if >= 0.75
```

---

### 2. Decision Consistency (Target: 100%)

**What It Measures**: How often the same decision state is used consistently within a cohort.

**Computation**:
```
For cohort (SPY, ETF, 2-6 weeks):
- Total decisions: 15
- Decision state distribution:
  - "watch": 8 (53%)
  - "pursue": 5 (33%)
  - "reject": 2 (13%)
- Consistency = max(8/15, 5/15, 2/15) = 53%
  OR measure as: dominant state frequency >= 70% is "consistent"
```

**Data Source**:
- `store.list_packets()` — group by (ticker, assetClass, timeHorizon)
- `packet.decisionState` — count by state
- `store._feedback_records` — outcomes per decision state

**Storage**:
```python
class DecisionConsistencyMetric:
    cohort: str  # "SPY/ETF/2-6 weeks"
    total_decisions: int
    dominant_state: str  # "watch"
    dominant_state_count: int
    consistency_score: float  # target: 1.0 (100%)
    status: "ok" | "warning"
```

---

### 3. Packet Integrity (Target: 90%)

**What It Measures**: Completeness of required packet fields (no null/missing critical data).

**Computation**:
```
For each packet, check required fields:
- ticker: required ✓
- assetClass: required ✓
- timeHorizon: required ✓
- confidence: required (0-100) ✓
- decisionState: required ✓
- thesis: required ✓
- claims: required (list) ✓

Packets with all 7 fields: 90 / 100 = 90%
Integrity = 90%
```

**Data Source**:
- `store.list_packets()`
- Check each packet for None/empty values in required fields

**Storage**:
```python
class PacketIntegrityMetric:
    total_packets: int
    complete_packets: int
    integrity_score: float  # target: 0.90
    incomplete_fields: dict[str, int]  # field_name -> count of missing
    status: "ok" | "warning"
```

---

### 4. Data Quality (Target: 95%)

**What It Measures**: Freshness and availability of market data in packets.

**Computation**:
```
Packets created: 100
- With market snapshot: 98
- With live data (not fallback): 95
- With <1min old data: 94

Data quality = (98 + 95 + 94) / 300 = 95.67%
OR: count packets with all three: 94 / 100 = 94%
```

**Data Source**:
- `packet.marketSnapshot` — exists?
- `packet.marketSnapshot.dataMode` — "live" vs "cached" vs "fallback"
- `packet.marketSnapshot.timestamp` — age in minutes
- `market_provider_status()` — live feed availability

**Storage**:
```python
class DataQualityMetric:
    total_packets: int
    with_market_data: int
    with_live_data: int  # not fallback
    with_fresh_data: int  # <5 min old
    quality_score: float  # target: 0.95
    fallback_count: int  # count using fallback
    status: "ok" | "degraded"
```

---

### 5. Agent Consensus (Target: 70%)

**What It Measures**: Agreement between specialist agents on key metrics (confidence, risk).

**Computation**:
```
For each packet with multiple specialist outputs:
- Confidence estimate from agents A, B, C: [65%, 68%, 63%]
- Std dev: 2.3%
- Consensus score: 1 - (std_dev / mean) = 1 - (2.3/65) = 96%

OR simpler: count packets where agent outputs agree on decision direction
- Agents recommend "watch": 85 / 100 = 85%
- Consensus at 70%+ threshold: ok
```

**Data Source**:
- `packet.agentOutputs` — dict of specialist outputs
- `packet.confidenceBreakdown` — component scores
- `packet.riskMonitor` — risk assessments

**Storage**:
```python
class AgentConsensusMetric:
    total_packets: int
    packets_multi_agent: int
    consensus_packets: int  # agreement detected
    avg_consensus_score: float  # target: 0.70
    divergence_count: int  # packets where agents disagree
    status: "ok" | "warning"
```

---

### 6. Backtest Validity (Target: 0.75 Correlation)

**What It Measures**: How well backtests predict live decision outcomes.

**Computation**:
```
For cohort (SPY, 2-6 weeks):
- Backtest prediction: 70% win rate expected
- Live outcome: 73% win rate observed
- Correlation (Spearman rank): 0.78

Target: correlation >= 0.75 (strong positive relationship)
```

**Data Source**:
- `packet.backtestResult` — predicted accuracy, Sharpe, max drawdown
- `store._feedback_records` — actual outcomes per cohort
- Compare predictions vs actual outcomes

**Storage**:
```python
class BacktestValidityMetric:
    total_cohorts: int
    cohorts_backtested: int
    avg_correlation: float  # Spearman correlation (target: 0.75)
    prediction_error: float  # RMSE between predicted and actual
    aligned_cohorts: int  # correlation >= 0.75
    status: "ok" | "warning"
```

---

### 7. Risk Estimate Accuracy (Target: 80%)

**What It Measures**: How often risk alerts match realized outcomes.

**Computation**:
```
Risk alerts issued: 100
- "High risk" alerts: 60
  - Actually resulted in losses: 48 (80% accuracy)
  - False positives: 12
- "Low risk" alerts: 40
  - No loss: 35 (87% accuracy)
  - False negatives: 5

Risk estimate accuracy = (48 + 35) / 100 = 83%
Target: >= 80%
```

**Data Source**:
- `packet.riskMonitor` — risk assessments
- `store._feedback_records` — actual outcomes
- Cross-reference risk level with outcome

**Storage**:
```python
class RiskEstimateMetric:
    total_packets: int
    high_risk_alerts: int
    high_risk_accurate: int  # actually lost
    low_risk_alerts: int
    low_risk_accurate: int  # didn't lose
    estimate_accuracy: float  # target: 0.80
    status: "ok" | "warning"
```

---

### 8. Confidence Calibration (Target: N% Confidence = N% Accuracy)

**What It Measures**: Overall platform confidence calibration (already partially done in Todo 2).

**Computation**:
```
By confidence band:
- 50-60%: target 55%, actual 52% ✓
- 60-70%: target 65%, actual 68% ✗ (over-confident)
- 70-80%: target 75%, actual 74% ✓
- 80-90%: target 85%, actual 83% ✓

Calibration = count(well-calibrated) / total_bands
= 3 / 4 = 75%
```

**Data Source**:
- Already computed in `store.get_calibration_summary()`
- Add per-band tracking and reporting

**Storage**:
```python
class ConfidenceCalibrationMetric:
    total_bands: int
    well_calibrated_bands: int  # within ±5% of target
    over_confident_bands: int
    under_confident_bands: int
    calibration_score: float  # target: >= 0.75 (75% of bands well-calibrated)
    status: "ok" | "warning"
```

---

## Implementation Approach (3 Phases)

### Phase 1: Create Metrics Data Models (1-2 hours)

**File**: Create `services/api/app/calibration_metrics.py`

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal

class ReviewValidityMetric(BaseModel):
    total_reviews: int = 0
    reviews_converted: int = 0
    conversion_rate: float = 0.0
    target: float = 0.75
    status: Literal["ok", "low"] = "ok"
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())

class DecisionConsistencyMetric(BaseModel):
    cohort: str
    total_decisions: int = 0
    dominant_state: str | None = None
    consistency_score: float = 0.0
    target: float = 1.0
    status: Literal["ok", "warning"] = "ok"

# ... (continue for all 8 metrics)

class CalibrationMetricsBoard(BaseModel):
    """Complete metrics snapshot for platform health."""
    review_validity: ReviewValidityMetric
    decision_consistency: dict[str, DecisionConsistencyMetric]
    packet_integrity: PacketIntegrityMetric
    data_quality: DataQualityMetric
    agent_consensus: AgentConsensusMetric
    backtest_validity: BacktestValidityMetric
    risk_estimate: RiskEstimateMetric
    confidence_calibration: ConfidenceCalibrationMetric
    
    computed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    overall_status: Literal["ok", "warning", "critical"] = "ok"
```

**Effort**: 1-2 hours

---

### Phase 2: Implement Metric Computation Functions (5-7 hours)

**File**: Same `calibration_metrics.py`

```python
def compute_review_validity(store) -> ReviewValidityMetric:
    """Compute review → packet conversion rate."""
    reviews = store.list_reviews()
    packets = store.list_packets()
    
    converted = 0
    for packet in packets:
        # Check if packet was created from a review
        for event in packet.audit:
            if event.eventType == "review.converted_to_packet":
                converted += 1
                break
    
    rate = converted / len(reviews) if reviews else 0.0
    return ReviewValidityMetric(
        total_reviews=len(reviews),
        reviews_converted=converted,
        conversion_rate=round(rate, 3),
        status="ok" if rate >= 0.75 else "low"
    )

def compute_decision_consistency(store) -> dict[str, DecisionConsistencyMetric]:
    """Compute consistency of decision states within cohorts."""
    # Group packets by (ticker, assetClass, timeHorizon)
    # Count decision states per cohort
    # Return metric for each cohort

def compute_packet_integrity(store) -> PacketIntegrityMetric:
    """Check completeness of required packet fields."""

def compute_data_quality(store) -> DataQualityMetric:
    """Measure freshness and availability of market data."""

def compute_agent_consensus(store) -> AgentConsensusMetric:
    """Measure agreement between specialist agents."""

def compute_backtest_validity(store) -> BacktestValidityMetric:
    """Correlate backtest predictions with live outcomes."""

def compute_risk_estimate_accuracy(store) -> RiskEstimateMetric:
    """Measure risk alert accuracy."""

def compute_confidence_calibration(store) -> ConfidenceCalibrationMetric:
    """Compute overall confidence calibration score."""

def compute_all_metrics(store) -> CalibrationMetricsBoard:
    """Compute all 8 metrics and return aggregated board."""
    return CalibrationMetricsBoard(
        review_validity=compute_review_validity(store),
        decision_consistency=compute_decision_consistency(store),
        packet_integrity=compute_packet_integrity(store),
        data_quality=compute_data_quality(store),
        agent_consensus=compute_agent_consensus(store),
        backtest_validity=compute_backtest_validity(store),
        risk_estimate=compute_risk_estimate_accuracy(store),
        confidence_calibration=compute_confidence_calibration(store),
    )
```

**Effort**: 5-7 hours (largest phase, most logic)

---

### Phase 3: Integration with Store & Health Check (2-3 hours)

**File Changes**:
1. Add to `ReviewStore` in `store.py`:
   ```python
   def get_calibration_metrics(self) -> CalibrationMetricsBoard:
       from .calibration_metrics import compute_all_metrics
       return compute_all_metrics(self)
   ```

2. Update `GET /health/detailed` in `main.py`:
   ```python
   @app.get("/health/detailed")
   def health_detailed() -> dict:
       # ... existing code ...
       metrics = store.get_calibration_metrics()
       
       return {
           "status": overall,
           "service": "ambrosia-api",
           "checks": {
               # ... existing checks ...
               "calibrationMetrics": {
                   "reviewValidity": {
                       "conversionRate": metrics.review_validity.conversion_rate,
                       "target": metrics.review_validity.target,
                       "status": metrics.review_validity.status
                   },
                   "packetIntegrity": {
                       "integrityScore": metrics.packet_integrity.integrity_score,
                       "target": metrics.packet_integrity.target,
                       "status": metrics.packet_integrity.status
                   },
                   # ... all 8 metrics ...
               }
           },
           # ... rest of response ...
       }
   ```

3. Optional: Add `GET /metrics` endpoint for detailed metrics view

**Effort**: 2-3 hours

---

## Testing Strategy

### Unit Tests (Per Metric)

```python
# services/api/tests/test_calibration_metrics.py

def test_review_validity_metric():
    """Test review → packet conversion calculation."""
    store = ReviewStore()
    # Create 10 reviews
    # Convert 7 to packets
    # Check metric returns 70% conversion
    metric = compute_review_validity(store)
    assert metric.conversion_rate == 0.70

def test_decision_consistency_metric():
    """Test decision state frequency calculation."""
    # Create 10 packets for same cohort
    # 7 "watch", 2 "pursue", 1 "reject"
    # Check consistency score is 0.70

def test_packet_integrity_metric():
    """Test missing field detection."""
    # Create packets with missing fields
    # Check integrity score reflects missing data

# ... continue for all 8 metrics
```

### Integration Test

```python
def test_all_metrics_computed():
    """Test that all 8 metrics compute without error."""
    store = ReviewStore()
    # Add test data (reviews, packets, feedback)
    metrics = compute_all_metrics(store)
    
    # Verify all metric fields populated
    assert metrics.review_validity.conversion_rate >= 0
    assert metrics.packet_integrity.integrity_score >= 0
    # ... 8 assertions total
    
    # Verify overall status determined
    assert metrics.overall_status in ["ok", "warning", "critical"]
```

### Manual Validation

```bash
# 1. Start API with new metrics
python -m uvicorn app.main:app --reload --port 8000

# 2. Query health endpoint
curl http://localhost:8000/health/detailed | jq '.checks.calibrationMetrics'

# 3. Verify all 8 metrics present and valid
# Expected output:
{
  "reviewValidity": {...},
  "decisionConsistency": {...},
  "packetIntegrity": {...},
  "dataQuality": {...},
  "agentConsensus": {...},
  "backtestValidity": {...},
  "riskEstimate": {...},
  "confidenceCalibration": {...}
}
```

---

## Success Criteria

✅ **All 8 metrics computed** and returned in health check  
✅ **All thresholds defined** (target values set)  
✅ **Status determination** (ok/warning/critical)  
✅ **Test coverage** (unit tests for each metric)  
✅ **Documentation** (metric formulas + data sources)  

**Exit Condition**: `GET /health/detailed` returns full `calibrationMetrics` object with all 8 metrics and overall platform status determined by metric health.

---

## Remaining After Todo 3

- **Todo 4**: Operational scorecard (4-6 hours) — packages metrics into certification-ready format
- **Final Integration**: Deploy to staging, run full validation, certify Index39 completion

---

## Execution Sequence

1. Create `calibration_metrics.py` with all data models
2. Implement compute functions one by one (test after each)
3. Integrate into `store.py` and `main.py`
4. Test locally, validate all metrics present
5. Deploy to staging for final validation
6. Move to Todo 4 (scorecard)

**Estimated Total**: 10-14 hours focused implementation
