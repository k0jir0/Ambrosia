# Phase A Production Deployment Runbook

## Overview
This runbook provides step-by-step instructions for deploying Phase A (Platform Hardening) to production on Render. It covers pre-deployment validation, deployment execution, post-deployment monitoring, and rollback procedures.

**Timeline**: Week 1 (Days 1-7)
**Target**: Production on Render (https://ambrosia-api.onrender.com, https://ambrosia-web.onrender.com)
**Deployment Type**: Zero-downtime rolling deployment

---

## Pre-Deployment (Day 1-2)

### 1.1 Prerequisites Checklist
- [ ] Render CLI installed: `npm install -g render-cli`
- [ ] Authenticated with Render: `render login`
- [ ] GitHub repository access confirmed
- [ ] All local dependencies installed: `pnpm install`
- [ ] All 48 core tests passing locally: `pnpm test:api`
- [ ] Web frontend builds: `pnpm build:web`
- [ ] API can import successfully: `python -c "from services.api.app.main import app; print('OK')"`
- [ ] Staging environment validated on Render
- [ ] Backup of current production data created
- [ ] On-call rotation scheduled for monitoring period

### 1.2 Pre-Deployment Testing
Run the complete test suite to ensure stability:

```bash
# Test API (48/48 required)
cd Ambrosia
pnpm test:api

# Expected output:
# ===== 48 passed in ~4.4s =====

# Build web frontend
pnpm build:web

# Expected output:
# ✓ Compiled successfully
```

### 1.3 Deployment Artifact Creation
Create and verify the deployment manifest:

```bash
# Run deployment script
bash scripts/phase-a-production-deploy.sh

# Verify artifacts created
ls -la artifacts/phase-a-deployment-*
# phase-a-deployment-manifest.json
# phase-a-deployment-report.md
# phase-a-deployment-TIMESTAMP.log
```

---

## Deployment Execution (Day 3-4)

### 2.1 Create Deployment Branch and PR
```bash
cd Ambrosia
git checkout -b deploy/phase-a-production

# Update render.yaml with any necessary changes
# (Already configured for ambrosia-api and ambrosia-web services)

git add render.yaml
git commit -m "chore: Phase A production deployment PR

- Component: Platform Hardening
- Endpoints: API + Web
- Tests: 48/48 passing
- Acceptance contracts: 4/4 ready
- Target: Production environment

Deployment checklist:
- [x] Tests passing
- [x] Build successful
- [x] Manifest created
- [x] Monitoring ready
"

git push origin deploy/phase-a-production
```

### 2.2 Create GitHub PR and Get Approval
```
PR Title: "chore: Phase A production deployment (Platform Hardening)"

Description should include:
- Phase overview
- All acceptance contracts status (4/4 passing)
- Test results (48/48 passing)
- Rollback plan
- Monitoring plan (48h baseline)
```

### 2.3 Merge to Main and Deploy
```bash
# After PR approval:
git checkout main
git pull origin main
git merge deploy/phase-a-production
git push origin main

# Render will automatically deploy on main push
# Deployment will start within 2-5 minutes
```

### 2.4 Monitor Deployment Progress
Monitor the Render dashboard for deployment status:
1. Navigate to: https://dashboard.render.com/
2. Select service: ambrosia-api
3. Check "Deploys" tab for status
4. Verify both ambrosia-api and ambrosia-web deploy successfully

Expected status progression:
- Building... (2-3 min)
- Deploying... (1-2 min)
- Live (with green checkmark)

---

## Post-Deployment Validation (Day 4-5)

### 3.1 Immediate Health Check (Within 10 minutes)
```bash
# Check API health endpoint
curl -s https://ambrosia-api.onrender.com/health | jq .

# Expected response:
# {
#   "status": "ok",
#   "service": "ambrosia-api",
#   "timestamp": "2026-06-26T..."
# }

# Check detailed health
curl -s https://ambrosia-api.onrender.com/health/detailed | jq .

# Check web application
curl -s https://ambrosia-web.onrender.com/ | head -20
# Should return HTML (Next.js app)
```

### 3.2 Phase A Acceptance Contract Validation
Test each of the 4 Phase A acceptance contracts:

**Contract 1: Retrieval Quality Benchmarks**
```bash
# This validates that retrieval quality data loads
curl -s https://ambrosia-api.onrender.com/calibration/metrics | jq '.retrieval_quality'

# Expected: Array of 5 benchmark results
```

**Contract 2: Calibration Metrics (8/8)**
```bash
curl -s https://ambrosia-api.onrender.com/calibration/metrics | jq '.metrics | length'

# Expected: 8 (8 calibration metrics)
```

**Contract 3: Scorecard Computation**
```bash
curl -s https://ambrosia-api.onrender.com/calibration/metrics | jq '.scorecard'

# Expected: Scorecard object with computed values
```

**Contract 4: Migration Framework**
```bash
# Verify database migrations applied
curl -s https://ambrosia-api.onrender.com/health/detailed | jq '.checks.database'

# Expected: { "status": "ok", ... }
```

### 3.3 Smoke Test Suite
Run automated smoke tests against production:

```bash
# Navigate to test directory
cd Ambrosia

# Run production smoke tests
bash scripts/phase-a-smoke-tests.sh production

# Expected output:
# ✓ API health check passed
# ✓ Web app responding
# ✓ Database connected
# ✓ All 4 acceptance contracts validated
# ===== SMOKE TESTS PASSED (5/5) =====
```

---

## Baseline Monitoring (Day 5-7)

### 4.1 Monitoring Dashboard Setup
1. Log into https://dashboard.render.com/
2. Navigate to both services:
   - ambrosia-api
   - ambrosia-web
3. Enable real-time logs
4. Set up email alerts for:
   - Deployment failure
   - Service down
   - High error rate (>1%)
   - High memory usage (>80%)

### 4.2 Metric Collection Schedule

**Hour 0-2: Immediate Health**
- [ ] Both endpoints responding
- [ ] No error spikes
- [ ] Database connections stable
- [ ] Latency <2s

**Hour 2-12: Functional Validation**
- [ ] All calibration endpoints working
- [ ] Test data loading correctly
- [ ] No 500 errors in logs
- [ ] Response times consistent

**Hour 12-48: Regression Monitoring**
- [ ] No cumulative errors
- [ ] Memory usage stable
- [ ] Latency percentiles consistent
- [ ] All metrics within normal range

### 4.3 Daily Metrics Report

Create daily status report (Template):
```
DATE: 2026-06-26 (Day 1 of monitoring)

API Metrics:
- Uptime: 100%
- Error rate: 0.0%
- P50 latency: 45ms
- P95 latency: 280ms
- P99 latency: 1,200ms
- Database queries: All OK
- Active connections: N

Web Metrics:
- Uptime: 100%
- Build time: 2.1s average
- Static asset delivery: <100ms
- No JS errors in console

Acceptance Contracts:
- [ ] Contract 1 (Retrieval): PASS
- [ ] Contract 2 (Metrics): PASS
- [ ] Contract 3 (Scorecard): PASS
- [ ] Contract 4 (Migration): PASS

Issues Found: None
Action Items: None
```

---

## Rollback Procedure (If Needed)

### 5.1 When to Rollback
Rollback is recommended if:
- Error rate exceeds 5%
- P99 latency exceeds 5 seconds
- Service downtime exceeds 15 minutes
- Critical data corruption detected
- Security vulnerability discovered

### 5.2 Rollback Steps
```bash
cd Ambrosia

# 1. Identify last known good commit
git log --oneline | head -5

# 2. Revert the deployment commit
git revert <commit-hash-of-phase-a-deployment>

# 3. Push revert to main
git push origin main

# 4. Render will automatically re-deploy (previous version)
# Monitor Render dashboard for deployment status

# 5. Verify rollback successful
curl -s https://ambrosia-api.onrender.com/health

# 6. Post-incident review
# - Document what went wrong
# - Create fix PR
# - Test thoroughly before re-deploying
```

---

## Phase A Go/No-Go Decision (Day 7)

### 6.1 Success Criteria
- [x] Zero-downtime deployment successful
- [x] All 4 acceptance contracts passing in production
- [x] 48+ hours of stable operation (no regressions)
- [x] Error rate <0.1%
- [x] Latency P99 <2 seconds
- [x] Database connections stable
- [x] All smoke tests passing
- [x] No critical issues in logs

### 6.2 Go/No-Go Sign-Off
```
Final Approval:

Phase A Production Deployment: GO ✓

- Deployment Date: 2026-06-26
- Monitoring Complete: 2026-06-28 (48h+ baseline)
- All 4 Contracts Passing: YES
- Status: PRODUCTION LIVE
- Completion Update: 92% → 93%

Signed:
- Engineering Lead: _________________ Date: _______
- Product Manager: _________________ Date: _______
- DevOps/SRE: _________________ Date: _______
```

### 6.3 Next Phase Activation
After Phase A go-live:
```bash
# Update completion artifacts
jq '.phase_a.status = "LIVE"' \
  artifacts/index59-100-percent-completion.json > temp.json
mv temp.json artifacts/index59-100-percent-completion.json

# Begin Phase B CI/CD setup
# (Week 2 work)
```

---

## Emergency Contacts

On-call rotation for 48h monitoring:
- Primary: [Engineering Lead]
- Secondary: [DevOps Engineer]
- Tertiary: [Backend Lead]

Escalation:
- Level 1: On-call engineer
- Level 2: Engineering Lead
- Level 3: VP Engineering / Product

---

## Phase A Deployment Timeline Summary

| Day | Task | Owner | Status |
|-----|------|-------|--------|
| 1-2 | Pre-deployment validation | Engineering | TODO |
| 3 | Create & approve deployment PR | Team | TODO |
| 4 | Deploy to production | DevOps | TODO |
| 5 | Immediate validation (smoke tests) | QA | TODO |
| 5-7 | 48h baseline monitoring | On-call | TODO |
| 7 | Go/No-Go decision | Leadership | TODO |
| 8+ | Begin Phase B CI/CD setup | Engineering | TODO |

---

## Document Information
- **Created**: 2026-06-25
- **Status**: Active Deployment Plan
- **Version**: 1.0
- **Next Review**: Post-deployment (Day 7)
