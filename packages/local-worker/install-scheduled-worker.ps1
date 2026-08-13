[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$TaskName = 'Ambrosia Staging Qwen Worker',
    [Parameter(Mandatory)] [ValidatePattern('^https://')] [string]$ApiUrl,
    [Parameter(Mandatory)] [string]$Model,
    [string]$PythonExecutable = 'python',
    [ValidateRange(8192, 8192)] [int]$ContextLength = 8192,
    [ValidateRange(256, 4096)] [int]$MaxOutputTokens = 1536
)

$ErrorActionPreference = 'Stop'
$workerPath = Join-Path $PSScriptRoot 'ambrosia_local_worker.py'
$launcherPath = Join-Path $PSScriptRoot 'run-scheduled-worker.ps1'
foreach ($requiredPath in @($workerPath, $launcherPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required worker file is missing: $requiredPath"
    }
}

$stateDirectory = Join-Path $env:LOCALAPPDATA 'Ambrosia\LocalWorker'
$configurationPath = Join-Path $stateDirectory 'staging-worker.json'
$credentialPath = Join-Path $stateDirectory 'staging-worker-token.clixml'
New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null

$token = Read-Host 'Paste the one-time Ambrosia worker credential' -AsSecureString
if ($token.Length -eq 0) { throw 'Worker credential cannot be empty.' }
$token | Export-Clixml -LiteralPath $credentialPath

[pscustomobject]@{
    apiUrl = $ApiUrl.TrimEnd('/')
    model = $Model
    pythonExecutable = $PythonExecutable
    contextLength = $ContextLength
    maxOutputTokens = $MaxOutputTokens
    installedAt = [DateTimeOffset]::UtcNow.ToString('o')
} | ConvertTo-Json | Set-Content -LiteralPath $configurationPath -Encoding UTF8

$arguments = @(
    '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
    '-File', ('"' + $launcherPath + '"'),
    '-WorkerPath', ('"' + $workerPath + '"'),
    '-ConfigurationPath', ('"' + $configurationPath + '"'),
    '-CredentialPath', ('"' + $credentialPath + '"')
) -join ' '
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 10 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Days 3650) `
    -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

if ($PSCmdlet.ShouldProcess($TaskName, 'Register persistent outbound Ollama worker')) {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force | Out-Null
    Start-ScheduledTask -TaskName $TaskName
}

[pscustomobject]@{
    taskName = $TaskName
    configurationPath = $configurationPath
    credentialPath = $credentialPath
    credentialProtection = 'Windows DPAPI, current-user scoped'
    apiUrl = $ApiUrl
    model = $Model
}
