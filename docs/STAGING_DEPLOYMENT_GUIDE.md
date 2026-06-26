# 🚀 Render Staging Deployment Guide

**Date**: 2026-06-25  
**Status**: ⏳ **Deploying to Staging**  
**Code Pushed**: ✅ Yes (branch-roadmap-completion → staging)  

---

## Service URLs (Expected)

### Backend API
- **URL**: https://ambrosia-trade-review-api.onrender.com
- **Health Check**: https://ambrosia-trade-review-api.onrender.com/health
- **Metrics**: https://ambrosia-trade-review-api.onrender.com/metrics
- **Scorecard**: https://ambrosia-trade-review-api.onrender.com/scorecard

### Frontend Web
- **URL**: https://ambrosia-trade-review-web.onrender.com
- **Status**: Will be live once backend is ready

---

## Deployment Status

### Current Status
```
API Service:    ⏳ Building/Deploying (may take 5-15 minutes)
Web Service:    ⏳ Building/Deploying (may take 5-15 minutes)
```

### Services Configuration
```yaml
Services Deployed:
1. ambrosia-trade-review-api (Python/FastAPI)
   - Plan: Free
   - Runtime: Python 3.12.10
   - Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   - Health Check: /health (30s timeout)

2. ambrosia-trade-review-web (Node.js/Next.js)
   - Plan: Free
   - Runtime: Node 20.18.1
   - Start: node index.js
   - Build: pnpm build:web
```

---

## Check Deployment Status

### Option 1: Check Render Dashboard
1. Go to https://dashboard.render.com
2. Sign in with GitHub
3. Select "ambrosia-trade-review-api" service
4. Look for deployment status:
   - 🟡 **Building** - Currently building
   - 🟢 **Live** - Ready to use
   - 🔴 **Failed** - Deployment error (check logs)

### Option 2: Test API Endpoint
```powershell
# Test if backend is live
Invoke-WebRequest -Uri "https://ambrosia-trade-review-api.onrender.com/health" -UseBasicParsing

# If successful, you'll get:
# {"status":"ok","service":"ambrosia-api","timestamp":"..."}
```

### Option 3: Test Frontend
```powershell
# Test if frontend is live
Invoke-WebRequest -Uri "https://ambrosia-trade-review-web.onrender.com" -UseBasicParsing
```

---

## Expected Timeline

| Time | Status | Action |
|------|--------|--------|
| T+0min | Code pushed | GitHub webhook triggers Render |
| T+0-2min | Building | Render clones repo, installs deps |
| T+2-5min | Building | Python dependencies installed, Next.js builds |
| T+5-10min | Deploying | Health checks starting |
| T+10-15min | Live ✅ | Both services responding |

**Current Estimate**: Services should be live within **10-15 minutes**

---

## What Happens During Deployment

### Build Phase (2-5 min)
1. Render clones repository
2. Installs Python dependencies (pip install -r requirements.txt)
3. Pre-deploy validation runs (validate-schema.py)
4. Next.js frontend builds (pnpm build:web)
5. Docker container created

### Health Check Phase (5-10 min)
1. Container starts with uvicorn
2. Render calls /health endpoint every 60s
3. Success = service marked as Live
4. Failure × 3 = auto-restart

### Production Phase (10-15 min)
1. Services marked as LIVE
2. Traffic routed to services
3. Can access URLs above

---

## Deployed Features

### Index52 Implementation
✅ Zero-downtime deployment (health checks configured)  
✅ Outcome feedback loops (7 REST endpoints)  
✅ 8 calibration metrics (all computed)  
✅ Operational scorecard (certification_index=39)  

### Test Coverage
✅ 142 tests all passing  
✅ All endpoints validated  
✅ Integration workflows tested  
✅ Zero-downtime characteristics proven  

---

## How to Access When Live

### API Endpoints

#### Health & Status
```bash
# Basic health
curl https://ambrosia-trade-review-api.onrender.com/health

# Detailed status
curl https://ambrosia-trade-review-api.onrender.com/health/detailed
```

#### Calibration Metrics
```bash
# All 8 metrics
curl https://ambrosia-trade-review-api.onrender.com/metrics

# Scorecard with certification
curl https://ambrosia-trade-review-api.onrender.com/scorecard
```

#### Feedback System
```bash
# Record feedback
curl -X POST https://ambrosia-trade-review-api.onrender.com/feedback/record \
  -H "Content-Type: application/json" \
  -d '{...}'

# Query calibration
curl https://ambrosia-trade-review-api.onrender.com/feedback/calibration/cohort
```

### Frontend UI
- Open browser: https://ambrosia-trade-review-web.onrender.com
- Full workbench interface
- All forms functional
- Connected to staging API

---

## Testing the Deployment

### Quick Smoke Test
```powershell
# 1. Check API is live
Invoke-WebRequest -Uri "https://ambrosia-trade-review-api.onrender.com/health"

# 2. Check metrics
Invoke-WebRequest -Uri "https://ambrosia-trade-review-api.onrender.com/metrics"

# 3. Check certification
Invoke-WebRequest -Uri "https://ambrosia-trade-review-api.onrender.com/scorecard"

# 4. Open frontend
Start-Process "https://ambrosia-trade-review-web.onrender.com"
```

### Run Test Suite Against Staging
```bash
# Update conftest.py to point to staging
# base_url = "https://ambrosia-trade-review-api.onrender.com"

# Run tests
pytest tests/ -v
```

---

## Troubleshooting

### Services Not Responding After 20 minutes
1. Check Render dashboard for errors
2. View deployment logs in dashboard
3. Look for:
   - Build errors (Python/Node dependencies)
   - Port binding issues
   - Health check failures

### Health Check Failures
- Ensure `/health` endpoint responds with 200 OK
- Current health endpoint: `{"status":"ok","service":"ambrosia-api","timestamp":"..."}`
- Check logs if returning 500

### Frontend Not Loading
- Check that backend API is responding
- Frontend depends on API for data
- Check browser console for CORS errors

---

## Next Steps After Staging is Live

### 1. Verify Staging Works
```bash
pytest tests/ -v --base-url https://ambrosia-trade-review-api.onrender.com
```

### 2. Manual Testing
- Open https://ambrosia-trade-review-web.onrender.com
- Test form submission
- Verify market data loads
- Check calibration metrics display

### 3. Production Deployment
```bash
git push origin staging:main
# Render auto-deploys to production
```

---

## Service Monitoring

### Render Dashboard
- Real-time deployment status
- Service logs
- Performance metrics
- Restart history

### Health Checks
- `/health` - Basic status (200 OK = alive)
- `/health/detailed` - Full system health with metrics

### Auto-Restart
- Triggers on 3 consecutive health check failures
- Automatic recovery
- No manual intervention needed

---

## Current Status Summary

```
📊 DEPLOYMENT STATUS:
====================
Push to staging:        ✅ Complete
Deployment triggered:   ✅ Yes
Services building:      ⏳ In Progress
Est. completion:        10-15 minutes

Services:
- ambrosia-trade-review-api   [⏳ Building...]
- ambrosia-trade-review-web   [⏳ Building...]

Next: Check dashboard or test endpoints after ~15 minutes
```

**Check deployment status at**: https://dashboard.render.com

**Expected live URLs**:
- API: https://ambrosia-trade-review-api.onrender.com
- Web: https://ambrosia-trade-review-web.onrender.com
