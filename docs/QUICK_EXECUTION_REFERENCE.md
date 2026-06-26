# Ambrosia: Quick Execution Reference

## Current Status
- **Overall Completion**: 91.7% (90.7% + 1% design refinement)
- **Target**: 100% by 2026-09-24 (Day 90)
- **Current Week**: Week 1 (Days 1-7)
- **Next Milestone**: Phase A Production Deployment

---

## Phase A: READY TO EXECUTE THIS WEEK

### Quick Start (5 steps)

```bash
# Step 1: Run deployment script
bash scripts/phase-a-production-deploy.sh

# Step 2: Monitor deployment (Render dashboard)
# https://dashboard.render.com/

# Step 3: Validate deployment
bash scripts/phase-a-smoke-tests.sh production

# Step 4: Begin 48h baseline monitoring
# Check every 2 hours for errors, latency, uptime

# Step 5: Day 7 Go/No-Go Decision
# All 4 contracts passing? → Phase B
```

### Key Files
- **Runbook**: `docs/PHASE_A_DEPLOYMENT_RUNBOOK.md` (detailed guide)
- **Script**: `scripts/phase-a-production-deploy.sh` (automated deployment)
- **Tests**: `scripts/phase-a-smoke-tests.sh` (10 validation tests)

### Timeline
- Mon-Tue: Pre-deployment validation & PR creation
- Wed-Thu: Deploy to production
- Fri-Sun: 48h baseline monitoring
- Day 7: Go/No-Go decision

### Success Criteria
- [x] Tests passing (48/48)
- [x] Build successful
- [x] Deployment script ready
- [x] Smoke tests ready
- [ ] Deployment executed
- [ ] 48h monitoring complete
- [ ] Go/No-Go approved

---

## Phase B: READY NEXT WEEK (Week 2)

### What to Do
1. Read: `docs/PHASE_B_CI_CD_SETUP.md`
2. Create GitHub Actions workflow
3. Implement B1-B4 CI/CD components

### Components
- **B1**: Provider Ablation (4 days)
- **B2**: Synthetic Monitoring (5 days)
- **B3**: Release Gates (4 days)
- **B4**: Function Registry (2 days)

### Timeline
- Days 15-16: B1 Provider Ablation
- Days 17-19: B2 Synthetic Monitoring
- Days 20-21: B3 Release Gates
- Days 22-23: B4 Function Registry
- Days 24-27: Test pipeline
- Day 28: Go/No-Go decision

---

## Phase C: STARTS WEEK 5

### What to Do
1. Read: `docs/PHASE_C_UI_INTEGRATION.md`
2. Build scanner discovery UI
3. Wire 25 panels to backend APIs

### Components
- **C1**: Discovery Scanner UI (5 days)
- **C2**: Report Export (4 days)
- **C3**: Analyst Shortcuts (3 days)
- **C4**: Panel Integration (3 days)

### Key Tasks
- [ ] Scanner UI at /discovery
- [ ] PDF/email report exports
- [ ] Batch thesis generation
- [ ] 25 panels integrated

---

## Phase D: STARTS WEEK 8

### Components
- Deploy RBAC middleware
- Enforce permission boundaries
- Build governance UI
- Create Advanced/Team/Admin tabs

### Timeline
- Days 46-49: RBAC deployment
- Days 50-52: Permission enforcement
- Days 53-55: Policy UI
- Days 56-59: Advanced/Team/Admin
- Day 60: Go/No-Go decision

---

## Phase E: STARTS WEEK 10

### Components
- Wire market data to sandbox
- Build attribution dashboard
- E2E certification

### Timeline
- Days 61-64: Market data
- Days 65-67: Attribution dashboard
- Days 68-70: E2E certification
- Days 71-75: Final validation
- Day 75: Go/No-Go decision

---

## Implementation Checklist

### Week 1 (Days 1-7) - CURRENT
- [x] Design debt fixed (4/5 critiques)
- [x] Phase A deployment scripts created
- [x] Phase A deployment runbook created
- [x] Phase A smoke tests created
- [ ] Phase A deployment executed
- [ ] 48h baseline monitoring started
- [ ] Phase A Go/No-Go approved

### Week 2-4 (Days 8-28) - PHASE B
- [ ] GitHub Actions workflow created
- [ ] B1 Provider Ablation integrated
- [ ] B2 Synthetic Monitoring deployed
- [ ] B3 Release Gates activated
- [ ] B4 Function Registry enforced
- [ ] CI/CD pipeline tested
- [ ] Phase B Go/No-Go approved

### Week 5-7 (Days 29-45) - PHASE C
- [ ] C1 Discovery scanner UI built
- [ ] C2 Report export UI built
- [ ] C3 Analyst shortcuts implemented
- [ ] C4 All 25 panels integrated
- [ ] Panel integration tested
- [ ] Phase C Go/No-Go approved

### Week 8-9 (Days 46-60) - PHASE D
- [ ] RBAC middleware deployed
- [ ] Permission boundaries enforced
- [ ] Policy configuration UI built
- [ ] Advanced/Team/Admin tabs created
- [ ] Governance UI tested
- [ ] Phase D Go/No-Go approved

### Week 10-11 (Days 61-75) - PHASE E
- [ ] Market data connected
- [ ] Attribution dashboard built
- [ ] E2E loop certified
- [ ] Final security review
- [ ] Phase E Go/No-Go approved

### Week 12 (Days 76-90) - FINAL
- [ ] All smoke tests passing
- [ ] Performance validation
- [ ] Leadership sign-off
- [ ] **100% COMPLETION**

---

## Key Endpoints to Monitor

### Phase A
- https://ambrosia-api.onrender.com/health
- https://ambrosia-web.onrender.com/

### Phase B (CI/CD)
- GitHub Actions: github.com/ambrosia/ambrosia-trade-review/actions
- Artifacts: artifacts/provider-ablation-*.json

### Phase C (Discovery)
- Scanner: /discovery
- Reports: /reports/{id}/export

### Phase D (Governance)
- Admin: /admin
- Team: /team
- Advanced: /advanced

### Phase E (Execution)
- Sandbox: /sandbox/positions
- Attribution: /attribution/{id}

---

## Documentation Reference

| File | Purpose |
|------|---------|
| `docs/PHASE_A_DEPLOYMENT_RUNBOOK.md` | Detailed Phase A procedures |
| `docs/PHASE_B_CI_CD_SETUP.md` | Phase B CI/CD implementation |
| `docs/PHASE_C_UI_INTEGRATION.md` | Phase C UI integration guide |
| `papers/index62.txt` | Overall status & roadmap |
| `papers/index61.txt` | Detailed 12-week roadmap |
| `docs/AUTOPILOT_CONTROL_CENTER.md` | Daily automation reference |

---

## Key Commands

```bash
# Phase A Deployment
bash scripts/phase-a-production-deploy.sh

# Phase A Validation
bash scripts/phase-a-smoke-tests.sh production

# Update Implementation Status
python scripts/update-implementation-status.py

# Run Local Tests
pnpm test:api

# Build Web Frontend
pnpm build:web
```

---

## Decision Gates (Go/No-Go)

| Gate | Date | Criteria |
|------|------|----------|
| Phase A | Day 7 | 48h monitoring complete, all contracts passing |
| Phase B | Day 28 | CI/CD pipeline operational, all gates working |
| Phase C | Day 45 | Discovery/reporting/workflow shipped, 25 panels integrated |
| Phase D | Day 60 | RBAC enforced, governance UI live |
| Phase E | Day 75 | E2E loop certified, all phases operational |
| **LAUNCH** | **Day 90** | **100% completion, external launch ready** |

---

## Blockers & Solutions

| Blocker | Solution | Status |
|---------|----------|--------|
| API won't start locally | Use Render production API | ✅ RESOLVED |
| Design debt in UI | Fixed 4/5 critiques | ✅ RESOLVED |
| Port binding issues | Not blocking (use Render) | ✅ RESOLVED |
| Phase C panels not integrated | Follow C4 integration checklist | ⏳ PENDING (Week 5) |

---

## Success Metrics

### Phase A (Day 7)
- ✓ Deployment successful (0 downtime)
- ✓ All 4 contracts passing
- ✓ P99 latency < 2s
- ✓ Error rate < 0.1%

### Phase B (Day 28)
- ✓ All gates automated
- ✓ No unauthorized deployments
- ✓ Evidence-backed releases
- ✓ Zero regressions

### Phase C (Day 45)
- ✓ Discovery scanner operational
- ✓ Reports exporting to PDF/email
- ✓ All 25 panels integrated
- ✓ Analyst velocity +15%

### Phase D (Day 60)
- ✓ RBAC enforced everywhere
- ✓ Multi-user teams operational
- ✓ Audit trail complete
- ✓ Governance UI live

### Phase E (Day 75)
- ✓ Paper trading operational
- ✓ Attribution analysis working
- ✓ E2E loop certified
- ✓ Ready for external launch

---

## Next Steps: START HERE

### This Week (Week 1)
1. **Read** `docs/PHASE_A_DEPLOYMENT_RUNBOOK.md`
2. **Execute** `bash scripts/phase-a-production-deploy.sh`
3. **Monitor** 48h baseline on Render dashboard
4. **Validate** `bash scripts/phase-a-smoke-tests.sh production`
5. **Decide** Day 7 Go/No-Go for Phase B

### Week 2
1. Read `docs/PHASE_B_CI_CD_SETUP.md`
2. Set up GitHub Actions workflow
3. Begin B1 provider ablation integration

### Week 5
1. Read `docs/PHASE_C_UI_INTEGRATION.md`
2. Begin C1 discovery scanner UI
3. Start panel integration work

---

**Status**: Ready to execute. All planning complete. Waiting on deployment authority.

---

Generated: 2026-06-26
Last Updated: 2026-06-26
Next Review: 2026-06-28 (Day 3 of Phase A)
