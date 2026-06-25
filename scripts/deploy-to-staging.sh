#!/bin/bash
# INDEX52 Staging Deployment Script
# Usage: ./scripts/deploy-to-staging.sh [staging-url]

set -e

STAGING_URL="${1:-https://api-staging.onrender.com}"
HEALTH_CHECK_RETRIES=10
HEALTH_CHECK_DELAY=15

echo "========================================"
echo "INDEX52 STAGING DEPLOYMENT WORKFLOW"
echo "========================================"
echo ""

# Step 1: Validate local code
echo "[1/6] Validating local code..."
python -m py_compile services/api/app/calibration_metrics.py services/api/app/operational_scorecard.py services/api/app/store.py services/api/app/main.py
if [ $? -eq 0 ]; then
    echo "✅ Syntax validation passed"
else
    echo "❌ Syntax validation failed"
    exit 1
fi

# Step 2: Run pre-deploy validation
echo ""
echo "[2/6] Running pre-deploy schema validation..."
python scripts/validate-schema.py
if [ $? -eq 0 ]; then
    echo "✅ Pre-deploy validation passed"
else
    echo "❌ Pre-deploy validation failed"
    exit 1
fi

# Step 3: Git commit and push
echo ""
echo "[3/6] Pushing code to staging branch..."
git add -A
git status --porcelain
read -p "Commit and push? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git commit -m "Index52: Deploy all 4 todos to staging" || echo "No changes to commit"
    git push origin HEAD:staging
    if [ $? -eq 0 ]; then
        echo "✅ Code pushed to staging"
    else
        echo "❌ Git push failed"
        exit 1
    fi
else
    echo "Aborted"
    exit 1
fi

# Step 4: Wait for deployment
echo ""
echo "[4/6] Waiting for Render deployment..."
echo "Render will automatically:"
echo "  • Run: python scripts/validate-schema.py (pre-deploy validation)"
echo "  • Deploy new instances with health checks"
echo "  • Gracefully drain old instances (30s window)"
echo ""
echo "Check deployment status at: https://dashboard.render.com"
read -p "Press Enter when deployment completes..."

# Step 5: Health check
echo ""
echo "[5/6] Validating deployment health..."
HEALTH_URL="$STAGING_URL/health"
retries=0
while [ $retries -lt $HEALTH_CHECK_RETRIES ]; do
    response=$(curl -s -w "\n%{http_code}" "$HEALTH_URL" 2>/dev/null || echo -e "\n000")
    http_code=$(echo "$response" | tail -n1)
    
    if [ "$http_code" = "200" ]; then
        echo "✅ Health check passed"
        echo "$response" | head -n -1 | jq .
        break
    else
        retries=$((retries + 1))
        if [ $retries -lt $HEALTH_CHECK_RETRIES ]; then
            echo "Waiting for deployment (attempt $retries/$HEALTH_CHECK_RETRIES)..."
            sleep $HEALTH_CHECK_DELAY
        fi
    fi
done

if [ $retries -ge $HEALTH_CHECK_RETRIES ]; then
    echo "❌ Health check timeout"
    exit 1
fi

# Step 6: Run smoke tests
echo ""
echo "[6/6] Running post-deployment smoke tests..."
python scripts/deploy-smoke-test.py "$STAGING_URL"
if [ $? -eq 0 ]; then
    echo "✅ All smoke tests passed"
else
    echo "⚠️  Some smoke tests failed"
fi

# Validation summary
echo ""
echo "========================================"
echo "DEPLOYMENT VALIDATION SUMMARY"
echo "========================================"
echo ""

echo "Fetching metrics..."
curl -s "$STAGING_URL/metrics" | jq '.overall_status'

echo ""
echo "Fetching scorecard..."
curl -s "$STAGING_URL/scorecard" | jq '{certification_status: .certification_status, all_metrics_present: .all_metrics_present, all_metrics_at_target: .all_metrics_at_target, gates_passed: .gates_passed}'

echo ""
echo "========================================"
echo "✅ STAGING DEPLOYMENT COMPLETE"
echo "========================================"
echo ""
echo "Next Steps:"
echo "1. Review metrics at: $STAGING_URL/health/detailed"
echo "2. Monitor for 5-10 minutes for any errors"
echo "3. When ready, deploy to production:"
echo "   git push origin staging:main"
echo ""
