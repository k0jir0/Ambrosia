#!/usr/bin/env pwsh
# promote.ps1 - Ambrosia Environment Promotion Script
#
# Usage:
#   .\scripts\promote.ps1 staging   # promote main → staging (fast-forward)
#   .\scripts\promote.ps1 production # promote staging → main
#
# This script ensures the standard promotion path:
#   feat/* → staging → main (production)

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("staging", "production")]
    [string]$Target
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "    ✓ $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    ⚠ $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "    ✗ $msg" -ForegroundColor Red }

$currentBranch = git rev-parse --abbrev-ref HEAD
Write-Step "Current branch: $currentBranch"

if ($Target -eq "staging") {
    Write-Step "Promoting current branch → staging"
    Write-Warn "This merges your current working branch into staging."
    Write-Warn "Ensure all local commits are pushed and CI passes first."

    $confirm = Read-Host "Promote '$currentBranch' to staging? (y/N)"
    if ($confirm -ne "y") { Write-Fail "Aborted."; exit 1 }

    git fetch origin
    git checkout staging
    git pull origin staging
    git merge $currentBranch --no-edit
    git push origin staging

    Write-OK "Promoted '$currentBranch' → staging"
    Write-OK "Render staging deploy will trigger automatically."
    Write-OK "Monitor: https://dashboard.render.com"

} elseif ($Target -eq "production") {
    Write-Step "Promoting staging → main (production)"
    Write-Warn "This promotes the current staging branch to production."
    Write-Warn "Ensure staging has been tested and is stable."

    $currentStagingCommit = git rev-parse origin/staging
    $stagingShort = $currentStagingCommit.Substring(0, 8)

    Write-Host "    Staging at: $stagingShort"

    $confirm = Read-Host "Promote staging ($stagingShort) to production? (y/N)"
    if ($confirm -ne "y") { Write-Fail "Aborted."; exit 1 }

    git fetch origin
    git checkout main
    git pull origin main
    git merge origin/staging --no-edit
    git push origin main

    Write-OK "Promoted staging → main (production)"
    Write-OK "Render production deploy will trigger automatically."
    Write-OK "Monitor: https://dashboard.render.com"
    Write-OK "Production URL: https://ambrosia-5aec.onrender.com"
}
