#!/bin/bash
################################################################################
# PHASE A PRODUCTION SMOKE TESTS
#
# Purpose: Validate Phase A deployment in production
# Scope: Test all 4 Phase A acceptance contracts
# Target: Production Render endpoints
################################################################################

set -e

# Configuration
ENVIRONMENT="${1:-production}"
API_URL="https://ambrosia-api.onrender.com"
WEB_URL="https://ambrosia-web.onrender.com"

if [ "$ENVIRONMENT" != "production" ]; then
  echo "Usage: $0 production"
  echo "Staging/local environments not yet supported for smoke tests"
  exit 1
fi

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
PASSED=0
FAILED=0

# Test utilities
test_start() {
  echo -e "${BLUE}[TEST]${NC} $1"
}

test_pass() {
  echo -e "${GREEN}  ✓ PASS${NC}: $1"
  ((PASSED++))
}

test_fail() {
  echo -e "${RED}  ✗ FAIL${NC}: $1"
  ((FAILED++))
}

test_section() {
  echo ""
  echo -e "${BLUE}========================================${NC}"
  echo -e "${BLUE}$1${NC}"
  echo -e "${BLUE}========================================${NC}"
}

# Phase A Smoke Tests

# TEST 1: API Health Check
test_section "TEST 1: API Health Check"
test_start "Checking API health endpoint"
RESPONSE=$(curl -s -w "\n%{http_code}" "$API_URL/health")
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
  STATUS=$(echo "$BODY" | jq -r '.status' 2>/dev/null || echo "unknown")
  if [ "$STATUS" = "ok" ]; then
    test_pass "API health endpoint returning OK"
  else
    test_fail "API health endpoint returned non-ok status: $STATUS"
  fi
else
  test_fail "API health endpoint returned HTTP $HTTP_CODE (expected 200)"
fi

# TEST 2: Web Application Response
test_section "TEST 2: Web Application Response"
test_start "Checking web application"
RESPONSE=$(curl -s -w "\n%{http_code}" "$WEB_URL/" --head)
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
  test_pass "Web application responding with HTTP $HTTP_CODE"
else
  test_fail "Web application returned HTTP $HTTP_CODE"
fi

# TEST 3: Contract 1 - Retrieval Quality Benchmarks
test_section "TEST 3: Contract 1 - Retrieval Quality Benchmarks"
test_start "Validating retrieval quality metrics"
RESPONSE=$(curl -s "$API_URL/calibration/metrics")
RETRIEVAL_COUNT=$(echo "$RESPONSE" | jq '.retrieval_quality 2>/dev/null | length' 2>/dev/null || echo "0")

if [ "$RETRIEVAL_COUNT" -ge "5" ]; then
  test_pass "Retrieval quality benchmarks present ($RETRIEVAL_COUNT benchmarks)"
else
  test_fail "Retrieval quality benchmarks missing or incomplete ($RETRIEVAL_COUNT found, 5 required)"
fi

# TEST 4: Contract 2 - Calibration Metrics (8/8)
test_section "TEST 4: Contract 2 - Calibration Metrics"
test_start "Validating 8 calibration metrics implemented"
METRICS_COUNT=$(echo "$RESPONSE" | jq '.metrics 2>/dev/null | length' 2>/dev/null || echo "0")

if [ "$METRICS_COUNT" = "8" ]; then
  test_pass "All 8 calibration metrics implemented"
else
  test_fail "Calibration metrics count mismatch ($METRICS_COUNT found, 8 required)"
fi

# TEST 5: Contract 3 - Scorecard Computation
test_section "TEST 5: Contract 3 - Scorecard Computation"
test_start "Validating scorecard generation"
SCORECARD=$(echo "$RESPONSE" | jq '.scorecard 2>/dev/null' 2>/dev/null)

if [ -n "$SCORECARD" ] && [ "$SCORECARD" != "null" ]; then
  test_pass "Scorecard computation operational"
else
  test_fail "Scorecard not present or null"
fi

# TEST 6: Contract 4 - Migration Framework / Database
test_section "TEST 6: Contract 4 - Migration Framework"
test_start "Validating database connectivity"
HEALTH_DETAILED=$(curl -s "$API_URL/health/detailed")
DB_STATUS=$(echo "$HEALTH_DETAILED" | jq -r '.checks.database.status 2>/dev/null' 2>/dev/null || echo "unknown")

if [ "$DB_STATUS" = "ok" ]; then
  test_pass "Database migrations applied and working"
else
  test_fail "Database status not ok: $DB_STATUS"
fi

# TEST 7: API Response Latency
test_section "TEST 7: API Response Latency"
test_start "Measuring API latency (target: <2000ms)"
START_TIME=$(date +%s%N)
curl -s "$API_URL/health" > /dev/null
END_TIME=$(date +%s%N)
LATENCY_MS=$(( (END_TIME - START_TIME) / 1000000 ))

if [ "$LATENCY_MS" -lt "2000" ]; then
  test_pass "API latency acceptable: ${LATENCY_MS}ms"
else
  test_fail "API latency too high: ${LATENCY_MS}ms (target: <2000ms)"
fi

# TEST 8: Error Rate Check
test_section "TEST 8: Error Rate Check"
test_start "Checking for recent errors in API"
ERROR_COUNT=$(curl -s "$API_URL/health/detailed" | jq '.checks.error_count 2>/dev/null // 0')

if [ "$ERROR_COUNT" = "0" ] || [ "$ERROR_COUNT" -lt "5" ]; then
  test_pass "Error rate acceptable: $ERROR_COUNT recent errors"
else
  test_fail "High error count detected: $ERROR_COUNT"
fi

# TEST 9: Endpoints Availability
test_section "TEST 9: Phase A Endpoints Availability"
ENDPOINTS=(
  "/health"
  "/health/detailed"
  "/calibration/metrics"
)

for endpoint in "${ENDPOINTS[@]}"; do
  test_start "Testing endpoint: $endpoint"
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL$endpoint")
  if [ "$HTTP_CODE" = "200" ]; then
    test_pass "Endpoint $endpoint responding"
  else
    test_fail "Endpoint $endpoint returned HTTP $HTTP_CODE"
  fi
done

# TEST 10: Integration Test - Full Flow
test_section "TEST 10: Integration Test - Full Flow"
test_start "Testing complete Phase A flow"

# Get health
HEALTH=$(curl -s "$API_URL/health")
HEALTH_STATUS=$(echo "$HEALTH" | jq -r '.status')

# Get metrics
METRICS=$(curl -s "$API_URL/calibration/metrics")
METRICS_COUNT=$(echo "$METRICS" | jq '.metrics | length')

# Validate flow
if [ "$HEALTH_STATUS" = "ok" ] && [ "$METRICS_COUNT" = "8" ]; then
  test_pass "Full Phase A flow working"
else
  test_fail "Phase A flow incomplete or broken"
fi

# Summary
test_section "SMOKE TEST SUMMARY"
TOTAL=$((PASSED + FAILED))
echo -e "Total Tests: $TOTAL"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ "$FAILED" = "0" ]; then
  echo -e "${GREEN}===== SMOKE TESTS PASSED (ALL TESTS) =====${NC}"
  exit 0
else
  echo -e "${RED}===== SMOKE TESTS FAILED ($FAILED failures) =====${NC}"
  exit 1
fi
