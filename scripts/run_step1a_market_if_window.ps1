param(
    [string]$Profile = "uk_paper",
    [int]$Runs = 3,
    [int]$PaperDurationSeconds = 1800,
    [ValidateSet("smoke", "orchestration", "reconcile", "qualifying")]
    [string]$RunObjectiveProfile = "qualifying",
    [int]$MinFilledOrders = 5,
    [double]$MinSymbolDataAvailabilityRatio = 0.80,
    [int]$PreflightMinBarsPerSymbol = 100,
    [string]$PreflightPeriod = "5d",
    [string]$PreflightInterval = "1m",
    [switch]$SkipSymbolAvailabilityPreflight,
    [switch]$AppendBacklogEvidence,
    [switch]$ClearKillSwitchBeforeEachRun,
    [int]$WindowStartUtcHour = 8,
    [int]$WindowEndUtcHour = 16
)

$ErrorActionPreference = "Stop"

if ($Profile -ne "uk_paper") {
    throw "Profile '$Profile' is not allowed for Step 1A market runs. Use --Profile uk_paper only."
}

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
    RunObjectiveProfile = $RunObjectiveProfile
    MinFilledOrders = $MinFilledOrders
    MinSymbolDataAvailabilityRatio = $MinSymbolDataAvailabilityRatio
    PreflightMinBarsPerSymbol = $PreflightMinBarsPerSymbol
    PreflightPeriod = $PreflightPeriod
    PreflightInterval = $PreflightInterval
    SkipSymbolAvailabilityPreflight = [bool]$SkipSymbolAvailabilityPreflight
    AppendBacklogEvidence = [bool]$AppendBacklogEvidence
    ClearKillSwitchBeforeEachRun = [bool]$ClearKillSwitchBeforeEachRun
}

& $marketScript @invokeParams

exit $LASTEXITCODE
