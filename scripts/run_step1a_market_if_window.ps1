param(
    [string]$Profile = "uk_paper",
    [int]$Runs = 3,
    [int]$PaperDurationSeconds = 1800,
    [int]$MinFilledOrders = 5,
    [switch]$AppendBacklogEvidence,
    [switch]$ClearKillSwitchBeforeEachRun,
    [int]$WindowStartUtcHour = 8,
    [int]$WindowEndUtcHour = 16
)

$ErrorActionPreference = "Stop"

$utcNow = (Get-Date).ToUniversalTime()
$hour = $utcNow.Hour
$inWindow = ($hour -ge $WindowStartUtcHour -and $hour -lt $WindowEndUtcHour)

Write-Host "Current UTC: $($utcNow.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "Allowed window (UTC): $WindowStartUtcHour`:00-$WindowEndUtcHour`:00"
Write-Host "In-window: $inWindow"

if (-not $inWindow) {
    Write-Host "Outside allowed window. Skipping market burn-in run."
    exit 2
}

$marketScript = Join-Path (Split-Path -Parent $PSCommandPath) "run_step1a_market.ps1"
if (-not (Test-Path $marketScript)) {
    throw "Market runner script not found: $marketScript"
}

$invokeParams = @{
    Profile = $Profile
    Runs = $Runs
    PaperDurationSeconds = $PaperDurationSeconds
    MinFilledOrders = $MinFilledOrders
    AppendBacklogEvidence = [bool]$AppendBacklogEvidence
    ClearKillSwitchBeforeEachRun = [bool]$ClearKillSwitchBeforeEachRun
}

& $marketScript @invokeParams

exit $LASTEXITCODE
