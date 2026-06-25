#!/usr/bin/env pwsh
# new-feature.ps1 - Create a new feature/fix/chore branch off staging
#
# Usage:
#   .\scripts\new-feature.ps1 feat index57-collaboration
#   .\scripts\new-feature.ps1 fix  feedback-record-null-check
#   .\scripts\new-feature.ps1 chore update-dependencies

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("feat", "fix", "chore")]
    [string]$Type,

    [Parameter(Mandatory=$true)]
    [string]$Name
)

$ErrorActionPreference = "Stop"

$branchName = "$Type/$Name"

Write-Host "`n==> Creating branch: $branchName" -ForegroundColor Cyan

git fetch origin
git checkout staging
git pull origin staging
git checkout -b $branchName

Write-Host "    ✓ Branch '$branchName' created from latest staging" -ForegroundColor Green
Write-Host "    ✓ Make your changes, then push and open a PR → staging" -ForegroundColor Green
Write-Host ""
Write-Host "    Push command:" -ForegroundColor Yellow
Write-Host "    git push origin $branchName" -ForegroundColor White
Write-Host ""
Write-Host "    PR: https://github.com/k0jir0/Ambrosia/compare/staging...$branchName" -ForegroundColor White
