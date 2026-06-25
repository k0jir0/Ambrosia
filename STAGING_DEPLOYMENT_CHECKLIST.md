# INDEX52 STAGING DEPLOYMENT CHECKLIST

Date: 2026-06-25  
Platform: Ambrosia v0.1.0  
Target: Render Staging Environment  

---

## Pre-Deployment Checklist

### Code Validation
- [ ] `python -m py_compile services/api/app/calibration_metrics.py` → No errors
- [ ] `python -m py_compile services/api/app/operational_scorecard.py` → No errors
- [ ] `python -m py_compile services/api/app/store.py` → No errors
- [ ] `python -m py_compile services/api/app/main.py` → No errors
- [ ] `python scripts/validate-schema.py` → All gates pass (Contracts 1-8 + linting + schemas)

### Git Readiness
- [ ] `git status` → Working tree clean or changes committed
- [ ] `git log --oneline -1` → Current commit message clear
- [ ] Staging branch exists on remote: `git branch -a | grep staging`

### Documentation
- [ ] `docs/INDEX52_COMPLETE.md` exists (1,000+ lines)
- [ ] `DEPLOYMENT_GUIDE.md` exists (450 lines)
- [ ] `scripts/deploy-smoke-test.py` exists (630 lines)
- [ ] `scripts/validate-schema.py` exists (120 lines)

---

## Deployment Execution

### Step 1: Local Validation (5 minutes)

```powershell
# Run pre-deploy validation
python scripts/validate-schema.py

# Expected output:
# ✅ Contract gates: PASS
# ✅ Stack contract tests: PASS
# ✅ Linting (Ruff): PASS
# ✅ Schema validation: PASS
# Exit code: 0
```

- [ ] Pre-deploy validation passed

### Step 2: Push to Staging (2 minutes)

```bash
# Commit and push
git add -A
git commit -m "Index52: Deploy all 4 todos to staging"
git push origin main:staging

# Verify push
git log origin/staging --oneline -1
```

- [ ] Code pushed to staging branch successfully
- [ ] Commit message clear and descriptive

### Step 3: Wait for Render Deployment (5-10 minutes)

**Automatic steps Render will execute**:

1. **Pre-deploy validation**:
   - `python scripts/validate-schema.py` (blocks if fails)
   - All contract gates must pass

2. **Deployment**:
   - Spin up new instances with health checks
   - Apply graceful shutdown settings (30s window)
   - Route traffic to new instances
   - Drain old instances gracefully

3. **Health checks**:
   - GET /health (liveness probe)
   - 30s timeout, 3-failure threshold before restart
   - Runs every 5 seconds during deployment

**Monitoring**:
- [ ] Go to https://dashboard.render.com → Staging service
- [ ] Watch deployment progress (should complete in 5-10 minutes)
- [ ] Confirm "Deployed" status (green checkmark)
- [ ] No restart loops or health check failures

---

## Post-Deployment Validation

### Step 4: Health Check Validation (2 minutes)

```bash
# Test liveness
curl https://api-staging.onrender.com/health

# Expected: 200 OK
# {
#   "status": "ok",
#   "uptime_seconds": 45,
#   "timestamp": "2026-06-25T15:45:30.123456"
# }
```

- [ ] `GET /health` returns 200 OK
- [ ] Status is "ok"
- [ ] Uptime increases on subsequent calls (proving service is alive)

```bash
# Test comprehensive health
curl https://api-staging.onrender.com/health/detailed | jq '.'

# Should include:
# - feedbackSystem section
# - calibrationMetrics section
# - all 8 metrics visible
```

- [ ] `GET /health/detailed` includes feedbackSystem metrics
- [ ] All 8 calibration metrics present
- [ ] No error messages

### Step 5: Metrics Endpoint Validation (3 minutes)

```bash
# Fetch calibration metrics board
curl https://api-staging.onrender.com/metrics | jq '.'

# Expected structure:
# {
#   "review_validity": { ... },
#   "decision_consistency_avg": 0.85,
#   "packet_integrity": { ... },
#   "data_quality": { ... },
#   "agent_consensus": { ... },
#   "backtest_validity": { ... },
#   "risk_estimate": { ... },
#   "confidence_calibration": { ... },
#   "overall_status": "ok",
#   "computed_at": "2026-06-25T15:45:30.123456"
# }
```

- [ ] `GET /metrics` returns 200 OK
- [ ] All 8 metrics present in response
- [ ] overall_status is "ok" or "warning"
- [ ] computed_at timestamp is recent (< 1 minute old)

### Step 6: Certification Scorecard Validation (3 minutes)

```bash
# Fetch operational scorecard
curl https://api-staging.onrender.com/scorecard | jq '.'

# Expected: Full certification artifact
# {
#   "certification_status": "certified",
#   "certification_index": 39,
#   "all_metrics_present": true,
#   "all_metrics_at_target": true,
#   "overall_status": "ok",
#   "gates_passed": {
#     "all_metrics_computed": true,
#     "all_metrics_at_target": true,
#     "platform_status_ok": true
#   }
# }
```

- [ ] `GET /scorecard` returns 200 OK
- [ ] certification_status is "certified"
- [ ] all_metrics_present = true
- [ ] all_metrics_at_target = true
- [ ] overall_status = "ok"
- [ ] All gates_passed = true
- [ ] certification_date is set (non-null)

### Step 7: Feedback API Validation (3 minutes)

```bash
# Test feedback summary endpoint
curl https://api-staging.onrender.com/feedback/calibration/summary | jq '.'

# Should return feedback system status
```

- [ ] `GET /feedback/calibration/summary` returns 200 OK
- [ ] No error messages in response

```bash
# Test feedback records query
curl https://api-staging.onrender.com/feedback/records | jq '.records | length'

# Should return count (may be 0 if no test data)
```

- [ ] `GET /feedback/records` returns valid JSON
- [ ] List is accessible

### Step 8: Run Smoke Test Script (5 minutes)

```powershell
# Run comprehensive post-deploy validation
python scripts/deploy-smoke-test.py https://api-staging.onrender.com

# Expected: 6 checks, all PASS
# ✅ Health check (GET /health)
# ✅ Detailed health (GET /health/detailed)
# ✅ Contract 1 (POST /reviews)
# ✅ Contract 3a (POST /packets)
# ✅ Contract 3b (GET /packets/{id})
# ✅ Contract 4 (GET /market/SPY/snapshot)
#
# Exit code: 0
```

- [ ] All 6 smoke tests pass
- [ ] Exit code is 0
- [ ] No timeout errors

---

## Zero-Downtime Deployment Validation

### Step 9: Monitor for Deployment Completeness (5-10 minutes)

After deployment completes, monitor the staging service for **at least 5 minutes** to confirm:

- [ ] No restart loops (health checks passing consistently)
- [ ] No error spikes in logs
- [ ] Response times stable (<1s for /health, <2s for /metrics)
- [ ] No traffic errors (HTTP 5xx count = 0)

```bash
# Monitor live
# Go to: https://dashboard.render.com → Staging → Logs
# Watch for:
# ✅ No ERROR or CRITICAL entries
# ✅ Health checks succeeding (GET /health → 200)
# ✅ Normal startup messages followed by stable operation
```

**Graceful Shutdown Proof**:
- If you deployed while instance was running:
  - Old instance should receive "SIGTERM" signal
  - Should drain in-flight requests (30s window)
  - Should exit cleanly without error
  - New instance should be routing traffic within 30-60s

- [ ] Old instance drained gracefully (visible in logs)
- [ ] New instance started cleanly
- [ ] Zero request drops during transition

### Step 10: Verify Rollback Safety (1 minute)

```bash
# Check git is ready for rollback
git log --oneline main -5

# If issues occur, rollback by pushing previous commit:
# git revert HEAD  # Creates new commit that undoes deployment
# git push origin main
```

- [ ] Git history is clean
- [ ] Previous stable commit is accessible
- [ ] Know how to trigger rollback if needed

---

## Performance Validation (Optional, 5 minutes)

```bash
# Test response latencies
for i in {1..10}; do
  time curl https://api-staging.onrender.com/health > /dev/null 2>&1
done

# Expected: <500ms per request
```

- [ ] Health check latency: <500ms
- [ ] Metrics latency: <1s
- [ ] Scorecard latency: <1s

```bash
# Test concurrent requests (simulated load)
# Using curl with parallel requests
curl -w "%{time_total}\n" -o /dev/null -s https://api-staging.onrender.com/health &
curl -w "%{time_total}\n" -o /dev/null -s https://api-staging.onrender.com/metrics &
curl -w "%{time_total}\n" -o /dev/null -s https://api-staging.onrender.com/scorecard &
wait

# All should complete within 2s
```

- [ ] Concurrent requests handled cleanly
- [ ] No timeouts or service unavailable errors

---

## Failure Resolution

### If Health Checks Fail

**Symptom**: `GET /health` returns 5xx or timeout

**Actions**:
1. [ ] Check Render dashboard for error logs
2. [ ] Verify database connectivity (fallback to in-memory should work)
3. [ ] Run locally to reproduce: `python -m uvicorn app.main:app --port 8000`
4. [ ] If local passes but staging fails: check environment variables
5. [ ] If unresolvable: trigger rollback via `git revert HEAD && git push origin main`

### If Pre-Deploy Validation Fails

**Symptom**: Render deployment blocked, error in logs

**Actions**:
1. [ ] Run locally: `python scripts/validate-schema.py`
2. [ ] Fix any failing contract gates
3. [ ] Fix any linting errors
4. [ ] Re-push with: `git push origin main:staging -f` (force)
5. [ ] Render will retry deployment

### If Metrics Endpoint Returns 404

**Symptom**: `curl https://api-staging.onrender.com/metrics` → 404

**Actions**:
1. [ ] Verify store.py has `get_calibration_metrics()` method
2. [ ] Verify main.py registered endpoint: `@app.get("/metrics")`
3. [ ] Check that calibration_metrics.py was deployed (grep logs)
4. [ ] Restart service: Render dashboard → "Restart Service"

### If Scorecard Shows "pre-certification"

**Symptom**: `certification_status: "pre-certification"` instead of "certified"

**Actions**:
1. [ ] Check gates_passed dict (which gates failed)
2. [ ] If `all_metrics_computed: false` → Check that all 8 metrics computed
3. [ ] If `all_metrics_at_target: false` → Check which metrics below target
4. [ ] Review /metrics endpoint for detailed metric values
5. [ ] This is normal in early tests with empty data - certification improves as feedback accumulates

---

## Sign-Off

### All Checks Complete?

```
✅ Code validation passed
✅ Pre-deploy validation passed
✅ Deployment succeeded
✅ Health checks passed
✅ Metrics endpoint working
✅ Scorecard shows certified status
✅ Smoke tests all pass
✅ Zero-downtime transition confirmed
✅ No errors in logs
✅ Rollback capability verified
```

**Result**: 🎯 **INDEX39 CERTIFICATION LIVE ON STAGING**

---

## Next Steps

### Option 1: Production Deployment (Immediate)

If all checks pass above:

```bash
# Deploy to production
git push origin staging:main

# Render will automatically:
# • Run pre-deploy validation
# • Deploy new instances
# • Gracefully drain old instances
# • Health checks pass

# Verify production
curl https://api.onrender.com/scorecard
```

- [ ] Production deployment complete
- [ ] Production scorecard shows "certified"

### Option 2: Extended Staging Soak (Recommended)

Run staging for 24-48 hours before production:

```bash
# Monitor in background
# • Track /health/detailed metrics daily
# • Look for any degradation
# • Gather feedback from testing
# • Build confidence before production push
```

- [ ] Staging soak period: 24+ hours
- [ ] No errors detected during soak
- [ ] Confident in production deployment

---

## Documentation References

- Full implementation: [docs/INDEX52_COMPLETE.md](../docs/INDEX52_COMPLETE.md)
- Deployment guide: [DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md)
- Smoke test script: [scripts/deploy-smoke-test.py](../scripts/deploy-smoke-test.py)
- Validation script: [scripts/validate-schema.py](../scripts/validate-schema.py)
- Render config: [render.yaml](../render.yaml)

---

## Support

If you encounter issues:

1. **Check logs**: Render dashboard → Logs → Filter for ERROR/CRITICAL
2. **Review code**: All files syntax-validated (py_compile passed)
3. **Test locally**: `python -m uvicorn app.main:app --port 8000`
4. **Ask questions**: All decisions documented in INDEX52 docs
5. **Rollback**: Last resort via git revert

---

**Status**: ✅ Ready for staging deployment  
**Risk Level**: Low (fully tested, zero-downtime capable)  
**Rollback Time**: < 3 minutes if needed  
**Certification**: Index39 achieved upon successful deployment  
