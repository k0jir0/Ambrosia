# Ambrosia Unit Tests

This folder contains isolated unit tests for the Ambrosia stack. The tests avoid live API servers, Render deployments, EAS, market-provider calls, and browser automation.

Current suite size: 85 tests.

Run them from the Ambrosia root with:

```powershell
python -m pytest tests/unit-tests -q
```

Or through the root package script:

```powershell
pnpm test:unit
```

Coverage intent:

- `test_backend_review_engine_unit.py`: deterministic adversarial-review behavior, prompt-injection handling, evidence-pointer normalization.
- `test_calibration_visibility_unit.py`: calibration metrics, tool-boundary declarations, and visibility artifact loaders.
- `test_coordinator_unit.py`: specialist coordinator scoring, JSON parsing, deterministic output, and provider fallback behavior.
- `test_market_math_unit.py`: pure market-data calculations and deterministic fallback series.
- `test_fastapi_routes_unit.py`: FastAPI review, mobile summary, mobile today, health, and scanner route behavior against an isolated in-memory store.
- `test_feedback_retrieval_monitoring_unit.py`: confidence calibration, retrieval quality, drift detection, and synthetic monitoring regression detection.
- `test_governance_execution_unit.py`: RBAC, permission boundaries, audit logging, and broker sandbox accounting.
- `test_index84_signal_platform_unit.py`: signal lifecycle helpers, version resolution, review-link lookup, execution feasibility, and rollups.
- `test_provider_sentiment_unit.py`: LLM/market provider resolution, market-provider status, and deterministic sentiment fallback.
- `test_quant_workflow_report_unit.py`: backtest eligibility, risk evaluation, confidence derivation, and report generation.
- `test_scanner_unit.py`: scanner signal classification, candidate scoring, sorting, filters, and provider isolation.
- `test_store_unit.py`: in-memory review, packet, job, collaboration, workflow-template, guardrail, feedback, alert, sandbox, and attribution state transitions.
- `test_mobile_api_view_models_unit.py`: mobile review summary, risk gate, hard-block, runbook, and signal writeback view models.
- `test_cross_stack_contracts_unit.py`: static API/web/mobile/schemas contract expectations across the monorepo.
