param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")

$venvAmbrosia = Join-Path $repoRoot ".venv\Scripts\ambrosia.exe"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (Test-Path $venvAmbrosia) {
    & $venvAmbrosia @CliArgs
    exit $LASTEXITCODE
}

if (Test-Path $venvPython) {
    & $venvPython -m ambrosia_cli.main @CliArgs
    exit $LASTEXITCODE
}

Write-Error "Could not find .venv\\Scripts\\ambrosia.exe or .venv\\Scripts\\python.exe under $repoRoot. Create the venv first."
exit 1
