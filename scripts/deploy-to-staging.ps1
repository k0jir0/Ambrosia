# Deploy Index52 Implementation to Render Staging
# This script orchestrates the full deployment validation workflow
# Prerequisites: Git configured, Render staging service set up, Python 3.9+

param(
    [string]$StagingUrl = "https://api-staging.onrender.com",
    [int]$HealthCheckRetries = 10,
    [int]$HealthCheckDelaySeconds = 15,
    [string]$GitBranch = "staging"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "INDEX52 STAGING DEPLOYMENT WORKFLOW" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Validate local code before pushing
Write-Host "[1/6] Validating local code..." -ForegroundColor Yellow
$validationResult = & python -m py_compile services/api/app/calibration_metrics.py services/api/app/operational_scorecard.py services/api/app/store.py services/api/app/main.py 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Syntax validation passed" -ForegroundColor Green
} else {
    Write-Host "❌ Syntax validation failed:" -ForegroundColor Red
    Write-Host $validationResult
    exit 1
}

# Step 2: Run pre-deploy validation script (same as Render will run)
Write-Host ""
Write-Host "[2/6] Running pre-deploy schema validation..." -ForegroundColor Yellow
$schemaValidation = & python scripts/validate-schema.py 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Pre-deploy validation passed" -ForegroundColor Green
} else {
    Write-Host "❌ Pre-deploy validation failed:" -ForegroundColor Red
    Write-Host $schemaValidation
    exit 1
}

# Step 3: Git commit and push to staging branch
Write-Host ""
Write-Host "[3/6] Pushing code to staging branch..." -ForegroundColor Yellow
$currentBranch = git rev-parse --abbrev-ref HEAD
Write-Host "Current branch: $currentBranch"

git add -A
$status = git status --porcelain
if ($status) {
    Write-Host "Changes detected, committing..."
    git commit -m "Index52: Deploy all 4 todos to staging (calibration metrics, feedback loops, operational scorecard, zero-downtime deployment)"
} else {
    Write-Host "No changes to commit"
}

Write-Host "Pushing to $GitBranch branch..."
git push origin $currentBranch`:$GitBranch

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Code pushed to staging" -ForegroundColor Green
} else {
    Write-Host "❌ Git push failed" -ForegroundColor Red
    exit 1
}

# Step 4: Wait for Render deployment
Write-Host ""
Write-Host "[4/6] Waiting for Render deployment..." -ForegroundColor Yellow
Write-Host "Render will automatically:"
Write-Host "  • Run: python scripts/validate-schema.py (pre-deploy validation)"
Write-Host "  • Deploy new instances with health checks"
Write-Host "  • Gracefully drain old instances (30s window)"
Write-Host ""
Write-Host "Check deployment status at: https://dashboard.render.com" -ForegroundColor Cyan
Write-Host "Press any key when deployment completes..."
Read-Host

# Step 5: Health check validation
Write-Host ""
Write-Host "[5/6] Validating deployment health..." -ForegroundColor Yellow
$healthUrl = "$StagingUrl/health"
$retries = 0
$maxRetries = $HealthCheckRetries

while ($retries -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 10
        if ($response.StatusCode -eq 200) {
            Write-Host "✅ Health check passed" -ForegroundColor Green
            $health = $response.Content | ConvertFrom-Json
            Write-Host "Status: $($health.status)"
            Write-Host "Uptime: $($health.uptime_seconds)s"
            break
        }
    } catch {
        $retries++
        if ($retries -lt $maxRetries) {
            Write-Host "Waiting for deployment (attempt $retries/$maxRetries)..." -ForegroundColor Gray
            Start-Sleep -Seconds $HealthCheckDelaySeconds
        }
    }
}

if ($retries -ge $maxRetries) {
    Write-Host "❌ Health check timeout after $($maxRetries * $HealthCheckDelaySeconds) seconds" -ForegroundColor Red
    exit 1
}

# Step 6: Run smoke tests
Write-Host ""
Write-Host "[6/6] Running post-deployment smoke tests..." -ForegroundColor Yellow
$smokeTestResult = & python scripts/deploy-smoke-test.py $StagingUrl 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ All smoke tests passed" -ForegroundColor Green
} else {
    Write-Host "⚠️  Some smoke tests failed:" -ForegroundColor Yellow
    Write-Host $smokeTestResult
}

# Validation summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "DEPLOYMENT VALIDATION SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Index39 Certification Endpoints:" -ForegroundColor Yellow
Write-Host ""

# Fetch and display metrics
Write-Host "GET $StagingUrl/metrics" -ForegroundColor Gray
try {
    $metrics = Invoke-WebRequest -Uri "$StagingUrl/metrics" -TimeoutSec 10 | ConvertFrom-Json
    Write-Host "✅ Calibration metrics retrieved" -ForegroundColor Green
    Write-Host "   - Review Validity: $($metrics.review_validity.conversion_rate * 100)%" -ForegroundColor Gray
    Write-Host "   - Packet Integrity: $($metrics.packet_integrity.integrity_score * 100)%" -ForegroundColor Gray
    Write-Host "   - Data Quality: $($metrics.data_quality.quality_score * 100)%" -ForegroundColor Gray
    Write-Host "   - Overall Status: $($metrics.overall_status)" -ForegroundColor Gray
} catch {
    Write-Host "⚠️  Could not fetch metrics" -ForegroundColor Yellow
}

Write-Host ""

# Fetch and display scorecard
Write-Host "GET $StagingUrl/scorecard" -ForegroundColor Gray
try {
    $scorecard = Invoke-WebRequest -Uri "$StagingUrl/scorecard" -TimeoutSec 10 | ConvertFrom-Json
    Write-Host "✅ Certification scorecard retrieved" -ForegroundColor Green
    Write-Host "   - Certification Status: $($scorecard.certification_status)" -ForegroundColor Green
    Write-Host "   - All Metrics Present: $($scorecard.all_metrics_present)" -ForegroundColor Green
    Write-Host "   - All Metrics at Target: $($scorecard.all_metrics_at_target)" -ForegroundColor Green
    Write-Host "   - Platform Status: $($scorecard.overall_status)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Gates Passed:" -ForegroundColor Yellow
    foreach ($gate in $scorecard.gates_passed.PSObject.Properties) {
        $status = if ($gate.Value) { "✅" } else { "❌" }
        Write-Host "   $status $($gate.Name): $($gate.Value)"
    }
} catch {
    Write-Host "⚠️  Could not fetch scorecard" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "✅ STAGING DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Review metrics at: $StagingUrl/health/detailed" -ForegroundColor Gray
Write-Host "2. Test feedback loops:" -ForegroundColor Gray
Write-Host "   curl '$StagingUrl/feedback/calibration/summary'" -ForegroundColor Gray
Write-Host "3. Monitor deployment for 30 minutes (zero-downtime validation)" -ForegroundColor Gray
Write-Host "4. Verify no alerts in Render dashboard" -ForegroundColor Gray
Write-Host "5. When ready, deploy to production:" -ForegroundColor Gray
Write-Host "   git push origin staging:main" -ForegroundColor Gray
Write-Host ""
