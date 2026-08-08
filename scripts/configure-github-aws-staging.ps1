[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$Repository = "k0jir0/Ambrosia",
    [string]$Environment = "staging",
    [string]$ReviewerLogin,
    [string]$AwsAccountId,
    [string]$AwsRegion = "ca-central-1",
    [string]$StateBucket,
    [string]$StateKmsKeyArn,
    [string]$DomainName,
    [string]$HostedZoneId,
    [string]$DeployRoleArn,
    [string]$AlbCertificateArn,
    [string]$CloudFrontCertificateArn,
    [string]$Owner,
    [string]$CostCenter,
    [string]$DataClassification = "synthetic",
    [string]$AlertEmail,
    [string]$BudgetName = "ambrosia-staging-monthly",
    [switch]$AllowPlanLimitedEnvironment,
    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
$RequiredVariables = @(
    "AWS_ACCOUNT_ID", "AWS_REGION", "TF_STATE_BUCKET", "TF_STATE_KMS_KEY_ARN",
    "DOMAIN_NAME", "HOSTED_ZONE_ID", "API_DESIRED_COUNT", "WEB_DESIRED_COUNT",
    "ALERT_EMAIL", "OWNER", "COST_CENTER", "DATA_CLASSIFICATION", "BUDGET_NAME"
)
$RequiredSecrets = @(
    "AWS_DEPLOY_ROLE_ARN", "ALB_CERTIFICATE_ARN", "CLOUDFRONT_CERTIFICATE_ARN"
)
$RequiredChecks = @(
    "API tests & lint",
    "Web build & lint",
    "Mobile contract & config",
    "Visibility proof gate",
    "Index84 web control-plane evidence",
    "dependency-audit",
    "postgres-integration",
    "validate",
    "PostgreSQL migration and tenant isolation",
    "Migration and schema versioning check"
)

function Invoke-GhJson {
    param([string[]]$Arguments, [object]$Body)
    $json = $Body | ConvertTo-Json -Depth 12 -Compress
    $result = $json | & gh @Arguments --input -
    if ($LASTEXITCODE -ne 0) { throw "gh command failed: gh $($Arguments -join ' ')" }
    return $result
}

function Assert-ConfiguredNames {
    param([string[]]$Actual, [string[]]$Required, [string]$Kind)
    $missing = @($Required | Where-Object { $_ -notin $Actual })
    if ($missing.Count -gt 0) {
        throw "Missing GitHub environment ${Kind}: $($missing -join ', ')"
    }
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is required."
}
& gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) { throw "GitHub CLI is not authenticated." }

$repoInfo = & gh api "repos/$Repository" | ConvertFrom-Json
if ($repoInfo.full_name -ne $Repository) { throw "Repository identity mismatch." }
& gh api "repos/$Repository/branches/staging" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "The remote staging branch does not exist." }

if (-not $VerifyOnly) {
    $values = @(
        $AwsAccountId, $StateBucket, $StateKmsKeyArn, $DomainName, $HostedZoneId,
        $DeployRoleArn, $AlbCertificateArn,
        $CloudFrontCertificateArn, $Owner, $CostCenter, $AlertEmail
    )
    if (-not $AllowPlanLimitedEnvironment) { $values += $ReviewerLogin }
    if ($values | Where-Object { [string]::IsNullOrWhiteSpace($_) }) {
        throw "All staging values and AlertEmail are required; ReviewerLogin is also required unless -AllowPlanLimitedEnvironment is explicit."
    }
    if ($Environment -ne "staging") { throw "Index133 permits this script to configure staging only." }
    if ($AwsRegion -ne "ca-central-1") { throw "AWS staging is restricted to ca-central-1." }
    if ($AwsAccountId -notmatch "^[0-9]{12}$") { throw "AwsAccountId must be 12 digits." }
    if ($DomainName -eq "example.com") { throw "A real Route53-managed domain is required." }
    if ($DataClassification -notin @("synthetic", "approved-staging")) {
        throw "DataClassification must be synthetic or approved-staging."
    }

    if ($AllowPlanLimitedEnvironment) {
        Write-Warning "GitHub environment reviewers are not being configured. The staging branch must retain an independent approval requirement."
        $environmentBody = @{
            can_admins_bypass = $false
            deployment_branch_policy = @{
                protected_branches = $false
                custom_branch_policies = $true
            }
        }
    } else {
        $reviewer = & gh api "users/$ReviewerLogin" | ConvertFrom-Json
        $environmentBody = @{
            wait_timer = 0
            prevent_self_review = $true
            can_admins_bypass = $false
            reviewers = @(@{ type = "User"; id = $reviewer.id })
            deployment_branch_policy = @{
                protected_branches = $false
                custom_branch_policies = $true
            }
        }
    }
    if ($PSCmdlet.ShouldProcess("$Repository environment $Environment", "Create and protect")) {
        Invoke-GhJson -Arguments @("api", "--method", "PUT", "repos/$Repository/environments/$Environment") -Body $environmentBody | Out-Null

        $policies = & gh api "repos/$Repository/environments/$Environment/deployment-branch-policies" | ConvertFrom-Json
        if (-not ($policies.branch_policies | Where-Object { $_.name -eq "staging" -and $_.type -eq "branch" })) {
            Invoke-GhJson -Arguments @("api", "--method", "POST", "repos/$Repository/environments/$Environment/deployment-branch-policies") -Body @{ name = "staging"; type = "branch" } | Out-Null
        }

        $variables = [ordered]@{
            AWS_ACCOUNT_ID = $AwsAccountId
            AWS_REGION = $AwsRegion
            TF_STATE_BUCKET = $StateBucket
            TF_STATE_KMS_KEY_ARN = $StateKmsKeyArn
            DOMAIN_NAME = $DomainName
            HOSTED_ZONE_ID = $HostedZoneId
            API_DESIRED_COUNT = "1"
            WEB_DESIRED_COUNT = "1"
            ALERT_EMAIL = $AlertEmail
            OWNER = $Owner
            COST_CENTER = $CostCenter
            DATA_CLASSIFICATION = $DataClassification
            BUDGET_NAME = $BudgetName
        }
        foreach ($entry in $variables.GetEnumerator()) {
            & gh variable set $entry.Key --repo $Repository --env $Environment --body $entry.Value
            if ($LASTEXITCODE -ne 0) { throw "Failed to set environment variable $($entry.Key)." }
        }

        $secrets = [ordered]@{
            AWS_DEPLOY_ROLE_ARN = $DeployRoleArn
            ALB_CERTIFICATE_ARN = $AlbCertificateArn
            CLOUDFRONT_CERTIFICATE_ARN = $CloudFrontCertificateArn
        }
        foreach ($entry in $secrets.GetEnumerator()) {
            $entry.Value | & gh secret set $entry.Key --repo $Repository --env $Environment
            if ($LASTEXITCODE -ne 0) { throw "Failed to set environment secret $($entry.Key)." }
        }

        $protectionBody = @{
            required_status_checks = @{ strict = $true; contexts = $RequiredChecks }
            enforce_admins = $true
            required_pull_request_reviews = @{
                dismiss_stale_reviews = $true
                require_code_owner_reviews = $false
                required_approving_review_count = 1
                require_last_push_approval = $true
            }
            restrictions = $null
            required_conversation_resolution = $true
            required_linear_history = $true
            allow_force_pushes = $false
            allow_deletions = $false
            block_creations = $false
        }
        Invoke-GhJson -Arguments @("api", "--method", "PUT", "repos/$Repository/branches/staging/protection") -Body $protectionBody | Out-Null
    }
}

$environmentInfo = & gh api "repos/$Repository/environments/$Environment" | ConvertFrom-Json
if (-not $environmentInfo.protection_rules) { throw "No environment protection rules are configured." }
if ($environmentInfo.can_admins_bypass -ne $false) {
    throw "Administrator bypass must be disabled for the staging environment."
}
$reviewerRules = @($environmentInfo.protection_rules | Where-Object { $_.type -eq "required_reviewers" })
if (-not $AllowPlanLimitedEnvironment -and $reviewerRules.Count -eq 0) {
    throw "The staging environment has no required-reviewer rule. Use -AllowPlanLimitedEnvironment only when the repository plan cannot provide it."
}
if ($environmentInfo.deployment_branch_policy.custom_branch_policies -ne $true) {
    throw "The environment is not restricted by custom deployment branch policy."
}
$policies = & gh api "repos/$Repository/environments/$Environment/deployment-branch-policies" | ConvertFrom-Json
if (-not ($policies.branch_policies | Where-Object { $_.name -eq "staging" -and $_.type -eq "branch" })) {
    throw "The staging-only deployment branch policy is missing."
}
$variableNames = @((& gh variable list --repo $Repository --env $Environment --json name | ConvertFrom-Json).name)
$secretNames = @((& gh secret list --repo $Repository --env $Environment --json name | ConvertFrom-Json).name)
Assert-ConfiguredNames -Actual $variableNames -Required $RequiredVariables -Kind "variables"
Assert-ConfiguredNames -Actual $secretNames -Required $RequiredSecrets -Kind "secrets"
$protection = & gh api "repos/$Repository/branches/staging/protection" | ConvertFrom-Json
if (-not $protection.required_pull_request_reviews -or -not $protection.required_status_checks.strict) {
    throw "Staging branch protection is incomplete."
}
if ($AllowPlanLimitedEnvironment -and $protection.required_pull_request_reviews.required_approving_review_count -lt 1) {
    throw "The plan-limited environment requires at least one independent staging branch approval."
}

Write-Host "Verified protected GitHub AWS staging control plane for $Repository."
Write-Host "Environment variables: $($RequiredVariables -join ', ')"
Write-Host "Environment secrets: $($RequiredSecrets -join ', ') (values not displayed)"
if ($AllowPlanLimitedEnvironment) {
    Write-Warning "Plan-limited mode verified: deployment approval is enforced by staging branch review, not an environment reviewer rule."
}
