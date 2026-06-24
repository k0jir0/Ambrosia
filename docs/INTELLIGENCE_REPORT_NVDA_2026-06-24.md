# Ambrosia Targeted Intelligence Report

**Date:** 2026-06-24  
**Ticker:** NVDA  
**Packet ID:** pkt-intel-64c2cc36  
**Scope:** One end-to-end intelligence pass through packet workflow, metrics, specialist routing, backtest gate, risk, portfolio context, and confidence derivation.

## 1) Executive Read

- Current stance: **Watch / conditional pursue**.
- Signal quality is mixed: technicals are not strongly directional (RSI ~45.67, sideways trend), sentiment is neutral, and risk is manageable but not green-lit for aggressive sizing.
- Backtest guardrails refused execution in this run (`ineligible`, `refused`), which is expected behavior under strict hygiene gates.
- Confidence landed at **60/100** with risk-adjusted confidence at **57/100**.

## 2) Provenance And Runtime Truth

- Provider requested: `hybrid`.
- Runtime provider used: `deterministic-engine`.
- Fallback used: **true**.
- Interpretation: model-capable path was not available at runtime for this run, and the system correctly disclosed fallback.

## 3) Inputs Used

- Thesis: AI infrastructure demand supports semiconductor leadership, with valuation and crowding risk.
- Horizon: 2-6 weeks.
- Expression: advisory long-bias with strict risk controls.
- Core disconfirming test: NVDA underperforms SOXX and QQQ over 10 sessions while realized volatility rises.

## 4) Intelligence Outputs

### Market / Technical / Sentiment

- Price snapshot: **408.5302**
- RSI: **45.6664**
- Trend: **sideways**
- Sentiment label: **neutral**
- Sentiment score: **50.0**

### Backtest / Risk / Confidence

- Backtest plan status: **ineligible**
- Backtest validity: **refused**
- Risk status: **monitoring**
- Overall confidence: **60**
- Risk-adjusted confidence: **57**

### Retrieval

- Hybrid retrieval hits for query `NVDA leadership volatility crowding`: **0**
- Note: this indicates sparse contextual memory for this exact query string in current stored artifacts.

## 5) Workflow Evidence

- Audit events recorded: **9**
- Workflow steps executed:
  1. Packet created
  2. Metrics refreshed
  3. Specialist agents run
  4. Backtest prepared
  5. Backtest executed (guardrail refusal)
  6. Risk evaluated
  7. Portfolio context updated
  8. Confidence derived
  9. Retrieval executed

## 6) Decision Guidance (Advisory)

- Keep status at **watch** until either:
  1. Trend transitions from sideways to sustained uptrend with RSI confirming strength, or
  2. Relative performance vs SOXX/QQQ improves while realized volatility remains controlled.
- Maintain strict position sizing limits and preserve refusal gates.
- Continue documenting disconfirming evidence to avoid momentum-only bias.

## 7) Non-Negotiable Compliance Check

- No fake live-data claim: **pass** (fallback disclosed)
- No hidden provenance: **pass** (provider fallback surfaced)
- No autonomous execution: **pass**
- No live broker mutation: **pass**
