# Run in a local interactive PowerShell. SSH reads the password from its console.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-zA-Z0-9.:-]+$')]
    [string]$TargetHost,
    [ValidateRange(1, 65535)]
    [int]$Port = 22,
    [ValidatePattern('^[a-zA-Z0-9_-]+$')]
    [string]$LoginUser = 'root'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$collectorPath = Join-Path $PSScriptRoot 'collect-baseline.sh'
$evidenceRoot = Join-Path $projectRoot 'evidence'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$reportPath = Join-Path $evidenceRoot "ssh-baseline-$timestamp.txt"
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
$previousEncoding = $OutputEncoding
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

Write-Host "Reading baseline from $LoginUser@$TargetHost`:$Port. Enter the SSH password when prompted."
Write-Host 'The collector reads hardware/system information; no installations, module loads or reboot.'
try {
    $collector = [System.IO.File]::ReadAllText($collectorPath).Replace("`r`n", "`n")
    $collector | & ssh -T -p $Port -o ConnectTimeout=8 -o ServerAliveInterval=10 `
        -o ServerAliveCountMax=2 -o StrictHostKeyChecking=accept-new `
        "$LoginUser@$TargetHost" 'sh -s' | Set-Content -LiteralPath $reportPath -Encoding UTF8
    $sshExit = $LASTEXITCODE
    $report = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8
    $hasBegin = $report -match '(?m)^TY1208Z_READONLY_BASELINE_BEGIN\r?$'
    $hasEnd = $report -match '(?m)^TY1208Z_READONLY_BASELINE_END\r?$'
    if ($sshExit -ne 0) {
        if ($hasBegin -and $hasEnd) {
            throw "SSH exited with code $sshExit after the report reached END. Review the saved report before repeating collection: $reportPath"
        }
        throw "SSH exited with code $sshExit. Partial output: $reportPath"
    }
    if (-not ($hasBegin -and $hasEnd)) {
        throw "Baseline incomplete. Partial output: $reportPath"
    }
    Write-Host "Baseline saved: $reportPath"
    Write-Host 'Return to the conversation and say the collection finished.'
} finally {
    $OutputEncoding = $previousEncoding
}
