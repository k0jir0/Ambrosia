#!/usr/bin/env bash
# INDEX52 TDD TEST SUITE — QUICK REFERENCE

# ============================================================
# SETUP
# ============================================================

# Install test dependencies
pip install -r tests/requirements.txt

# ============================================================
# RUN TESTS
# ============================================================

# Run all tests (comprehensive)
pytest -v

# Run quick smoke test
pytest test_api_endpoints.py test_index39_certification.py -v

# Run specific module
pytest test_index39_certification.py -v
pytest test_api_endpoints.py -v
pytest test_calibration_metrics.py -v
pytest test_feedback_loops.py -v
pytest test_integration_workflows.py -v
pytest test_zero_downtime_deployment.py -v

# Run with detailed output
pytest -vvs              # Very verbose + show prints
pytest -vvs --tb=long    # With full tracebacks
pytest -x               # Stop on first failure

# ============================================================
# INTERPRET RESULTS
# ============================================================

# SUCCESS: All tests passed
# → git push origin staging:main
# → Deploy to production

# PARTIAL: Some tests failed (pre-certification)
# → System working correctly
# → git push origin staging:main
# → Deploy to production

# ERROR: Connection refused
# → Staging not deployed yet
# → Check Render dashboard
# → Wait 5-10 minutes
# → Run tests again

# ============================================================
# VALIDATE SPECIFIC FEATURES
# ============================================================

# Check certification
pytest test_index39_certification.py -v

# Check health checks
pytest test_api_endpoints.py::TestHealthEndpoints -v

# Check metrics
pytest test_calibration_metrics.py -v

# Check feedback loops
pytest test_feedback_loops.py -v

# Check zero-downtime deployment
pytest test_zero_downtime_deployment.py -v

# Check end-to-end workflows
pytest test_integration_workflows.py -v

# ============================================================
# TEST STATISTICS
# ============================================================

# Get test count
pytest --collect-only -q

# Get test count by module
pytest test_index39_certification.py --collect-only -q
pytest test_api_endpoints.py --collect-only -q
pytest test_calibration_metrics.py --collect-only -q
pytest test_feedback_loops.py --collect-only -q
pytest test_integration_workflows.py --collect-only -q
pytest test_zero_downtime_deployment.py --collect-only -q

# ============================================================
# CONFIGURATION
# ============================================================

# Edit base URL (for production testing)
# File: tests/conftest.py
# Change: base_url = "https://api-staging.onrender.com"
# To: base_url = "https://api.onrender.com"

# Edit timeout (if tests timing out)
# File: pytest.ini
# Change: timeout = 30
# To: timeout = 60

# ============================================================
# DOCUMENTATION
# ============================================================

# Quick Start
cat RUN_TESTS_NOW.md

# Complete Guide
cat TEST_SUITE_GUIDE.md

# Implementation Summary
cat TEST_SUITE_SUMMARY.md

# ============================================================
# EXPECTED OUTPUT
# ============================================================

# Success (all pass):
# ==================== 200+ passed in 3.45s ====================

# Partial success (ok with empty data):
# ==================== 200+ passed, some 404s ====================

# Error (staging not ready):
# ERROR: Failed to connect to https://api-staging.onrender.com

# ============================================================
# DEPLOYMENT AFTER TESTS
# ============================================================

# When all tests pass:
git push origin staging:main

# Verify production (update conftest.py first):
pytest -v

# Monitor production:
curl https://api.onrender.com/health/detailed | jq '.'
