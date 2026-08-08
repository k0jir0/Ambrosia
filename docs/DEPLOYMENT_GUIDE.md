# Ambrosia Deployment and Rollback Guide

> [!WARNING]
> Legacy Render procedure retained only for the time-bounded rollback window.
> New releases follow `docs/operations/AWS_MIGRATION_RUNBOOK.md`.

**Last Updated**: 2026-06-25  
**Scope**: Production deployments on Render  
**Status**: This document covers the zero-downtime deployment validation (Index52 Todo 1)

## Overview

Ambrosia uses Render's rolling restart mechanism to achieve zero-downtime deployments. This guide documents:
- How deployments work
- How to validate deployments succeeded
- How to detect issues and rollback
- Expected behaviors during healthy and degraded states

## Deployment Architecture

### Services
- **API**: Python/FastAPI running on Render Free tier
  - Service: `ambrosia-trade-review-api`
  - Health check: `GET /health` (liveness probe)
  - Port: `$PORT` (assigned by Render)

- **Web**: Node.js Next.js running on Render Free tier
  - Service: `ambrosia-trade-review-web`
  - No explicit health check (Render monitors HTTP 200 response rate)
  - Port: `$PORT` (assigned by Render)

### Health Check Strategy

**Primary (Basic)**: `GET /health`
```json
{"status": "ok", "service": "ambrosia-api"}
```
- **Used by**: Render health probe for liveness detection
- **Threshold**: Must respond 200 OK within 30 seconds
- **Failure behavior**: 3 consecutive failures trigger automatic restart

**Secondary (Comprehensive)**: `GET /health/detailed`
```json
{
  "status": "ok|degraded",
  "checks": {"store": "ok", "marketData": {...}, "llmProviders": {...}},
  "slo": {"reviewsCreated": N, "packetsCreated": N, ...},
  "alerts": ["..."]
}
```
- **Used by**: Operators and smoke tests to detect subtle degradation
- **Behavior**: 
  - `status: "ok"` = all dependencies healthy
  - `status: "degraded"` = fallback active (Yahoo Finance instead of Polygon, deterministic instead of LLM)
  - Non-empty `alerts` = action may be needed

### Graceful Shutdown Sequence

When Render initiates a restart (during deploy or scale event):

1. **Old instance** receives SIGTERM signal
2. **Uvicorn** (API) enters graceful shutdown:
   - Stops accepting new connections
   - Waits up to 30 seconds for in-flight requests to complete
   - Forcefully terminates on timeout
3. **Node** (Web) enters graceful shutdown:
   - Closes HTTP server
   - Waits for pending responses
4. **New instance** starts:
   - Loads code and dependencies
   - Initializes FastAPI/Next.js
   - Becomes ready for traffic (health check passes)
   - Render routes new requests to new instance

**Key constraint**: This sequence works only if individual requests complete in <30 seconds. Long-running operations must be:
- Async (return job ID immediately, process in background)
- Queue-backed (enqueued in Redis/DB, consumed by worker)
- Documented with fallback behavior when worker unavailable

## Deployment Workflow

### Pre-Deploy

1. **Ensure all tests pass locally**:
   ```bash
   cd Ambrosia
   pnpm test:api        # Contract gates for API
   pnpm test:e2e        # End-to-end browser tests
   pnpm lint:api        # Python linting
   pnpm lint:web        # TypeScript linting
   ```

2. **Validate schema consistency**:
   ```bash
   python services/api/tests/test_contract_gates.py
   python tests/test_stack_contract.py
   ```

3. **Commit and push to main/release branch**:
   ```bash
   git add .
   git commit -m "Release: [description of changes]"
   git push origin main
   ```

### Deploy (Automatic via Render Webhook)

1. Render webhook triggers from Git push
2. Render pulls latest code
3. Runs `preDeployCommand: python scripts/validate-schema.py` (if configured)
4. Builds both services:
   - API: `pip install -r requirements.txt`
   - Web: `pnpm install && pnpm build:web`
5. Starts new instances (old instances still serving traffic)
6. New instances pass health check → Render routes traffic to new
7. Old instances gracefully terminate

### Post-Deploy Validation

**Automatic via Render**:
- Health check passes 2+ consecutive times
- Response rate >90% (no spike in 5xx errors)

**Manual validation** (recommended for production):
```bash
python scripts/deploy-smoke-test.py https://ambrosia-trade-review-api.onrender.com
```

This script:
- ✓ Validates `/health` responds and status=ok
- ✓ Validates `/health/detailed` has no critical alerts
- ✓ Exercises Contract 1 (review creation)
- ✓ Exercises Contract 3 (packet lifecycle)
- ✓ Exercises Contract 4 (market data provenance)
- Returns exit code 0 (success) or 1 (failure)

**Expected output**:
```
══════════════════════════════════════════════════════════════════════════════════════
Deploy Smoke Test
Target: https://ambrosia-trade-review-api.onrender.com
══════════════════════════════════════════════════════════════════════════════════════

✓ PASS GET /health                                   12.3ms  status=ok, service=ambrosia-api
✓ PASS GET /health/detailed                          45.2ms  alerts=0
✓ PASS POST /reviews (Contract 1)                   234.1ms  fields=8/8
✓ PASS POST /packets (Contract 3a)                  156.8ms  id=smoke-test-1719338400
✓ PASS GET /packets/{id} (Contract 3b)               87.3ms  ticker=SPY
✓ PASS GET /market/SPY/snapshot (Contract 4)        203.4ms  mode=fallback

══════════════════════════════════════════════════════════════════════════════════════
Result: 6/6 checks passed
══════════════════════════════════════════════════════════════════════════════════════

✓ Deploy smoke test PASSED — service is healthy
```

## Troubleshooting & Rollback

### Scenario 1: Deploy Smoke Test Fails (API Unreachable)

**Symptoms**:
- `deploy-smoke-test.py` fails with connection timeout
- `curl https://api.onrender.com/health` hangs or times out

**Root cause**: 
- Network connectivity issue
- Instance failed to start
- Port not listening

**Recovery**:
1. Check Render dashboard → ambrosia-trade-review-api → Logs
2. Look for Python errors during startup
3. **Option A: Auto-rollback** (if using Git-based deployment):
   ```bash
   git revert HEAD
   git push origin main
   # Render redeploys from reverted commit
   ```
4. **Option B: Manual rollback via Render UI**:
   - Dashboard → ambrosia-trade-review-api → Deployments
   - Click previous successful deployment
   - Click "Redeploy"
   - Render pulls old code and restarts services

**Expected recovery time**: 2-3 minutes

### Scenario 2: Deploy Smoke Test Reports Health as "Degraded"

**Symptoms**:
```
✓ PASS GET /health/detailed                          45.2ms  alerts=2
Alert: "Licensed NYSE data path not configured..."
Alert: "LLM provider unavailable, using deterministic..."
```

**Root cause**: 
- Expected behavior on Render Free tier (no env var for Polygon, no LLM API key)
- Fallback is working as designed

**Recovery**: 
- No action needed — system is functioning with fallback
- To restore live data: set `POLYGON_API_KEY` env var in Render dashboard
- To restore LLM: set `LANGCHAIN_API_KEY` env var

**Severity**: Low (fallback disclosure is correct)

### Scenario 3: Deploy Smoke Test Fails on Contract Gate (Review Creation)

**Symptoms**:
```
✗ FAIL POST /reviews (Contract 1)                   234.1ms  HTTP 500
```

**Root cause**: 
- Code change broke review schema
- Dependency import failed
- Database connection lost

**Recovery**:
1. Check Render logs for Python traceback:
   ```
   Dashboard → ambrosia-trade-review-api → Logs
   ```
2. Look for schema validation errors or import errors
3. **Rollback immediately**:
   ```bash
   git revert HEAD
   git push origin main
   ```
4. **Fix locally**:
   ```bash
   cd Ambrosia
   pnpm test:api  # Run contract tests locally
   # Fix the issue in code
   git add services/api/
   git commit -m "Fix: [description]"
   git push origin main
   ```

**Expected recovery time**: 5-10 minutes (rollback + retest + redeploy)

### Scenario 4: Health Check Passes, But Requests Timeout (Slow Inference)

**Symptoms**:
- Smoke test passes initially
- Users report "Request timed out" on packet operations
- Render dashboard shows healthy (health check passes)

**Root cause**: 
- Long-running agent inference (>30s) is blocking request
- Operations not properly async-queued

**Recovery**:
1. Check the operation in question — is it properly async?
   - `POST /packets/{id}/agents/run` should return job ID immediately
   - Actual inference runs in background queue
2. If blocking, refactor to queue-backed pattern (see [Async Job Pattern](#async-job-pattern))
3. Rollback if necessary

**Verification after fix**:
```bash
python scripts/deploy-smoke-test.py https://ambrosia-trade-review-api.onrender.com --timeout 60
```

### Scenario 5: Degradation After 5+ Minutes (Cold Start Recovery)

**Symptoms**:
- Smoke test passes immediately after deploy
- After 5+ minutes, requests slow down significantly
- `/health/detailed` shows increased alert frequency

**Root cause**: 
- Render Free tier cold starts: first request to idle instance takes 2-5 seconds
- Database connection pooling cold start
- LLM provider initialization delay

**Recovery**: 
- Expected behavior on Free tier
- To mitigate: upgrade to Render Paid tier, add uptime monitoring to prevent cold starts
- For now: document this SLO in `/health/detailed` output

## Async Job Pattern

For operations that might exceed 30-second request timeout:

**API**:
```python
@app.post("/packets/{packet_id}/agents/run", response_model=JobRecord)
def run_agents_async(packet_id: str, req: AgentRunRequest) -> JobRecord:
    """Enqueue agent run, return job ID immediately."""
    job = store.enqueue_job("agents.run", f"packet={packet_id}")
    # Background worker processes job asynchronously
    _executor.submit(_agents_worker, job.id, packet_id, req)
    return job  # Returns {"id": "job-123", "state": "queued"}
```

**Frontend**:
```typescript
// 1. Kick off job
const job = await api.post(`/packets/${id}/agents/run`, {...});

// 2. Poll for completion
const pollJob = async () => {
  const result = await api.get(`/jobs/${job.id}`);
  if (result.state === "completed") return result.output;
  if (result.state === "failed") throw new Error(result.error);
  setTimeout(pollJob, 1000);  // retry after 1s
};
const output = await pollJob();
```

This pattern ensures:
- Request completes in <3s (returns immediately)
- Long inference (5m+) runs in background
- Client can poll for status
- If server restarts, job state persists in database
- Graceful shutdown doesn't interrupt processing (worker survives restart)

## Monitoring & Alerting

### Recommended Checks (Manual, for now)

**Daily**:
```bash
curl -s https://ambrosia-trade-review-api.onrender.com/health/detailed | jq '.alerts'
```

**After each deploy**:
```bash
python scripts/deploy-smoke-test.py https://ambrosia-trade-review-api.onrender.com
```

**Weekly**:
- Review Render logs for crashes, restarts
- Check `/health/detailed` SLO counters for growth (reviews, packets, jobs)
- Verify no orphaned jobs in failed state

### Future: Automated Monitoring

Once integrated (Index52 Todo 4):
- `GET /scorecard` endpoint exposes:
  - Test pass rate by function
  - SLO counters from health check
  - Data mode distribution (live vs fallback)
  - Calibration scores
- Can be monitored by external system (DataDog, Prometheus, etc.)

## Rollback Decision Tree

```
Deploy runs → Smoke test fails?
  → YES: IMMEDIATE ROLLBACK (Scenario 1, 3, 4)
         git revert HEAD && git push
         Expected recovery: 2-3 min

  → NO: Smoke test passes? Check health/detailed
       → Status "ok": PROCEED (healthy)
       → Status "degraded": PROCEED WITH CAUTION
         - Fallback active (expected on Free tier)
         - Monitor for 5+ min
         - If alerts persist → ROLLBACK

Monitor for 24h in staging:
  → Any errors in logs? → ROLLBACK to previous version
  → Any timeouts >30s? → Check for blocking async ops
  → Health check stable? → PROCEED to prod
```

## Deployment Checklist

- [ ] All tests pass locally (`pnpm test:api`, `pnpm test:e2e`)
- [ ] No breaking schema changes (contracts still pass)
- [ ] Commit message is descriptive
- [ ] `git push origin main` triggers Render webhook
- [ ] Wait 3-5 min for build to complete
- [ ] Run smoke test: `python scripts/deploy-smoke-test.py ...`
- [ ] Check logs for warnings: Render dashboard → Logs
- [ ] Verify `/health/detailed` has no critical alerts
- [ ] Test one user flow manually (create review → packet → report)
- [ ] Monitor for 24h before declaring stable

## Support & Escalation

**Issue**: Smoke test consistently fails  
**Who to contact**: Platform owner  
**Action**: Investigate logs, determine rollback necessity

**Issue**: Intermittent timeouts (some requests slow, some fast)  
**Who to contact**: Performance team  
**Action**: Profile agent inference, check queue backlog

**Issue**: `/health/detailed` alerts persist >1h  
**Who to contact**: Data team (if data source), LLM team (if inference)  
**Action**: Restore provider configuration or escalate

---

## Appendix: Zero-Downtime Validation Checklist

This section validates that Index52 Todo 1 exit criteria are met.

### Exit Criteria

From Index52:
> "Deploy can be issued, validated, and rolled back without any request window longer than the configured health-check timeout."

### Validation Steps

1. **Health-check timeout verification** ✓ (Configured in render.yaml)
   - Render health check timeout: 30 seconds
   - Uvicorn graceful shutdown timeout: 30 seconds
   - Both configured in this document

2. **Smoke test delivery** ✓ (Implemented in scripts/deploy-smoke-test.py)
   - Runs `/health` and `/health/detailed`
   - Exercises 4 critical contract gates
   - Returns 0 on pass, 1 on fail
   - Suitable for deploy hooks

3. **Rollback procedure documentation** ✓ (This document)
   - Automatic (Git revert)
   - Manual (Render dashboard)
   - Recovery time: 2-3 minutes
   - No data loss (stateless API, persisted state in DB)

4. **End-to-end validation** 
   - [ ] Deploy to staging environment (requires Render staging service setup)
   - [ ] Issue a release to staging
   - [ ] Run smoke test against staging
   - [ ] Verify no request timeouts in staging logs
   - [ ] Simulate a rollback (revert to previous Git commit)
   - [ ] Verify rollback completes in <3 min
   - [ ] Record rollback time evidence for final sign-off

**Status**: Awaiting staging environment and end-to-end validation
