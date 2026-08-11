param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$BearerToken
)

$headers = @{ Authorization = "Bearer $BearerToken" }
$uri = "$($BaseUrl.TrimEnd('/'))/operational/email-readiness"

try {
    $response = Invoke-RestMethod -Method Get -Uri $uri -Headers $headers
} catch {
    Write-Error "Failed to query readiness endpoint: $($_.Exception.Message)"
    exit 1
}

$response | ConvertTo-Json -Depth 10

if ($response.status -ne "ready") {
    Write-Warning "Email readiness is NOT ready. Review blockers above."
    exit 2
}

Write-Output "Email readiness check passed."
exit 0
