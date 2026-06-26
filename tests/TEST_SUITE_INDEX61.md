# INDEX61 Comprehensive Test Suite

This directory contains the complete test suite for the INDEX61 roadmap implementation of the Ambrosia platform. The tests validate all 5 phases, 18 acceptance contracts, and complete system integration.

## Test Files Overview

### Core Phase Tests

#### `test_phase_c_discovery.py` (200+ tests)
Tests for Phase C: Discovery & Intelligence
- **Discovery Engine Tests**: Thesis generation from signals, retrieval, saving
- **Report Generator Tests**: Report creation, PDF/HTML/email export
- **Analyst Workflows**: Triage workflow, prioritized queue, bulk operations
- **Signal-to-Report Workflow**: Complete end-to-end discovery workflow
- **Contract Validation**: C1 (Discovery), C2 (Reports), C3 (Workflows)

Key test classes:
- `TestDiscoveryEngine` - Thesis generation endpoints
- `TestReportGenerator` - Report export functionality
- `TestAnalystWorkflows` - Optimization shortcuts
- `TestSignalToReportWorkflow` - Complete workflow
- `TestDiscoveryContract` - Acceptance contract validation

#### `test_phase_d_rbac.py` (150+ tests)
Tests for Phase D: Enterprise Governance & RBAC
- **RBAC Roles**: 4 roles with level-based permissions
- **Permission Boundaries**: 4 boundaries with risk levels
- **Audit Logging**: Privileged action tracking
- **Role Enforcement**: Header-based role checks
- **Privilege Escalation Protection**: Role restrictions
- **Contract Validation**: D1-D4 RBAC contracts

Key test classes:
- `TestRBACRoles` - Role definitions and hierarchy
- `TestPermissionBoundaries` - Boundary enforcement
- `TestAuditLogging` - Audit trail verification
- `TestRoleEnforcement` - Role header validation
- `TestPrivilegeEscalation` - Security checks
- `TestRBACContract` - Contract validation

#### `test_phase_e_execution.py` (180+ tests)
Tests for Phase E: Execution Loop Completion
- **Paper Trading**: Order execution, position management
- **Market Data**: Live quotes retrieval, multiple symbols
- **Attribution Analysis**: Performance tracking, factor analysis
- **E2E Certification**: Certification status and checklist
- **Contract Validation**: E1-E3 execution contracts

Key test classes:
- `TestPaperTradingSandbox` - Trading operations
- `TestMarketDataConnectivity` - Market data endpoints
- `TestAttributionAnalysis` - Performance analysis
- `TestE2ECertification` - Certification endpoints
- `TestExecutionContract` - Contract validation

#### `test_index61_completion.py` (100+ tests)
Tests for INDEX61 Completion Status & Tracking
- **Completion Status**: Overall platform completion
- **Phases Summary**: All 5 phases status
- **Acceptance Contracts**: 18/18 contracts validation
- **Deployment Readiness**: Production readiness checks
- **Roadmap Metrics**: Timeline and execution metrics
- **Certification Sign-Off**: Leadership approval endpoint

Key test classes:
- `TestCompletionStatus` - Overall progress
- `TestPhasesSummary` - Phase-by-phase breakdown
- `TestAcceptanceContracts` - Contract tracking
- `TestDeploymentReadiness` - Production checks
- `TestRoadmapMetrics` - Timeline metrics
- `TestCertificationSignOff` - Sign-off validation

#### `test_index61_integration.py` (120+ tests)
Full Stack Integration Tests
- **Cross-Phase Integration**: Phase dependencies and data flow
- **RBAC Across Boundaries**: Role enforcement integration
- **Complete Workflows**: Signal → Discovery → Execution
- **Data Integrity**: Consistent behavior across phases
- **Error Recovery**: Graceful degradation
- **System Robustness**: Resilience testing
- **System Verification**: Complete INDEX61 validation

Key test classes:
- `TestPhaseABIntegration` - Hardening + CI/CD
- `TestPhaseCDIntegration` - Discovery + RBAC
- `TestPhaseDEIntegration` - RBAC + Execution
- `TestFullSignalToTradeWorkflow` - Complete workflow
- `TestCrossPhaseDataIntegrity` - Data flow validation
- `TestIndex61SystemVerification` - Final validation

### Existing Tests

#### `test_api_endpoints.py`
Health checks and basic endpoint availability

#### `test_calibration_metrics.py`
Calibration system validation

#### `test_feedback_loops.py`
Feedback collection and processing

#### `test_integration_workflows.py`
System integration workflows

#### `test_stack_contract.py`
Contract validation framework

#### `test_zero_downtime_deployment.py`
Deployment safety checks

## Running the Tests

### Run all tests:
```bash
pytest tests/ -v
```

### Run specific test file:
```bash
pytest tests/test_phase_c_discovery.py -v
```

### Run specific test class:
```bash
pytest tests/test_phase_d_rbac.py::TestRBACRoles -v
```

### Run specific test:
```bash
pytest tests/test_phase_e_execution.py::TestPaperTradingSandbox::test_execute_order_endpoint -v
```

### Run with coverage:
```bash
pytest tests/ --cov=services.api.app --cov-report=html
```

### Run with markers:
```bash
pytest tests/ -m "phase_c or phase_d"
```

## Test Structure

Each test file follows consistent patterns:

### Test Classes
- Organized by feature/component
- Named with `Test*` prefix
- Each test class focuses on one area

### Test Methods
- Named with `test_*` prefix
- Include docstrings describing what's tested
- Use descriptive assertion messages
- Follow Arrange-Act-Assert pattern

### Test Fixtures
All tests use these fixtures from `conftest.py`:
- `api_client` - HTTP client for API testing
- `sample_packet_data` - Sample investment data
- `sample_feedback_data` - Sample feedback
- `sample_review_data` - Sample review
- `assert_helpers` - Custom assertions

## Acceptance Contract Coverage

### Phase A Contracts
- **A1**: Persistence & Versioning (covered in Phase B tests)
- **A2**: Retrieval Quality Metrics (covered in integration tests)
- **A3**: Calibration & Scorecard (covered in calibration tests)
- **A4**: Feedback System (covered in feedback tests)

### Phase B Contracts
- **B1**: Provider Ablation (GitHub Actions workflow)
- **B2**: Synthetic Monitoring (CI/CD tests)
- **B3**: Release Gates (CI/CD tests)
- **B4**: Function Registry (API endpoint tests)

### Phase C Contracts
- **C1**: Discovery Engine ✅ `test_phase_c_discovery.py`
- **C2**: Report Generator ✅ `test_phase_c_discovery.py`
- **C3**: Analyst Workflows ✅ `test_phase_c_discovery.py`

### Phase D Contracts
- **D1**: RBAC Engine ✅ `test_phase_d_rbac.py`
- **D2**: Permission Boundaries ✅ `test_phase_d_rbac.py`
- **D3**: Policy Configuration ✅ `test_phase_d_rbac.py`
- **D4**: Advanced/Team/Admin UI ✅ `test_phase_d_rbac.py`

### Phase E Contracts
- **E1**: Broker Sandbox ✅ `test_phase_e_execution.py`
- **E2**: Attribution Analysis ✅ `test_phase_e_execution.py`
- **E3**: Final Certification ✅ `test_phase_e_execution.py`

## Test Endpoints

### Phase C Discovery Endpoints
```
POST   /discovery/generate-thesis
GET    /discovery/recent-theses
POST   /discovery/save-thesis
POST   /discovery/reports/generate
POST   /discovery/reports/export-pdf
POST   /discovery/reports/export-html
POST   /discovery/reports/email-report
POST   /discovery/analyst/triage
GET    /discovery/analyst/queue
POST   /discovery/analyst/bulk-action
POST   /discovery/signal-to-thesis
```

### Phase D RBAC Endpoints
```
GET    /index61/rbac/roles
GET    /index61/rbac/audit-log
GET    /index61/rbac/permission-boundaries
```

### Phase E Execution Endpoints
```
POST   /execution/trading/execute-order
GET    /execution/trading/paper-positions
POST   /execution/trading/close-position
GET    /execution/trading/order-history
GET    /execution/market-data/live-quotes
POST   /execution/attribution/analyze
GET    /execution/attribution/dashboard
GET    /execution/attribution/factor-analysis
GET    /execution/attribution/performance-metrics
GET    /execution/certification/status
GET    /execution/certification/checklist
POST   /execution/certification/sign-off
```

### INDEX61 Status Endpoints
```
GET    /index61/completion/status
GET    /index61/phases/summary
GET    /index61/acceptance-contracts
GET    /index61/deployment-readiness
GET    /index61/roadmap-metrics
POST   /index61/certification/sign-off
```

## Test Data & Fixtures

### Common Test Data
```python
# Signal
{
    "id": "sig_001",
    "ticker": "NVDA",
    "signal_type": "momentum",
    "strength": 0.85
}

# Trade Order
{
    "ticker": "NVDA",
    "quantity": 100,
    "order_type": "market",
    "side": "buy"
}

# RBAC Headers
{"X-User-Role": "analyst"}  # or "user", "team_lead", "admin"
```

## Integration Testing

### Complete Workflow Tests
The `test_index61_integration.py` file validates complete workflows:

1. **Signal → Discovery → Execution**
   - Generate thesis from signal (Phase C)
   - Create report from thesis
   - Execute trade based on discovery (Phase E)

2. **RBAC Enforcement Across Phases**
   - Analyst can access discovery
   - User cannot create theses
   - Team lead can approve trades

3. **Data Integrity**
   - RBAC consistently enforced
   - Audit logging captures all actions
   - Cross-phase data flows correctly

4. **System Robustness**
   - Invalid data rejected gracefully
   - Concurrent access works
   - Health checks after workflows

## Test Configuration

### API Client Settings
- **Base URL**: `http://127.0.0.1:8001` (configurable)
- **Timeout**: 10 seconds
- **Retries**: 3 attempts on timeout
- **Retry Delay**: 0.5 seconds

### Test Execution
- **Scope**: Session-level fixtures for efficiency
- **Markers**: Can tag tests by phase
- **Parallelization**: Tests can run in parallel
- **Coverage**: Aimed at >80% code coverage

## Expected Test Results

### Passing Criteria
✅ All Phase C discovery endpoints responsive  
✅ All Phase D RBAC checks enforced  
✅ All Phase E trading operations functional  
✅ All INDEX61 status endpoints returning data  
✅ Complete workflows succeed end-to-end  
✅ RBAC enforced across all phases  
✅ All 18 acceptance contracts validated  
✅ 100% completion status reported  

### Known Limitations
- PDF export may return 501 (not implemented)
- Market data may return 503 (no external feed)
- Some endpoints may require authentication headers
- Paper trading is sandbox-only (no real execution)

## Troubleshooting

### API Server Not Running
```bash
cd services/api
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### Import Errors
```bash
cd Ambrosia
pip install -r services/api/requirements.txt
```

### Test Failures
1. Check API server is running on port 8001
2. Verify all phase modules are in `services/api/app/`
3. Check PYTHONPATH includes `services/api`
4. Review test output for specific failure reasons

## Coverage Goals

- **Phase C Discovery**: 85%+ coverage
- **Phase D RBAC**: 90%+ coverage  
- **Phase E Execution**: 80%+ coverage
- **INDEX61 Status**: 90%+ coverage
- **Integration**: 75%+ coverage
- **Overall**: 85%+ coverage

## Contributing Tests

When adding new tests:
1. Follow existing naming conventions
2. Use clear, descriptive test names
3. Include docstrings explaining what's tested
4. Use appropriate fixtures
5. Add contract validation tests
6. Update this README with new endpoints/coverage
