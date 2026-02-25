param(
    [string]$Profile = "uk_paper",
    [int]$Runs = 3,
    [int]$PaperDurationSeconds = 1800,
    [int]$MinFilledOrders = 5,
    [double]$MinSymbolDataAvailabilityRatio = 0.80,
    [int]$PreflightMinBarsPerSymbol = 100,
    [string]$PreflightPeriod = "5d",
    [string]$PreflightInterval = "1m",
    [switch]$SkipSymbolAvailabilityPreflight,
    [switch]$AppendBacklogEvidence,
    [switch]$ClearKillSwitchBeforeEachRun
)

$ErrorActionPreference = "Stop"

if ($Profile -ne "uk_paper") {
    throw "Profile '$Profile' is not allowed for Step 1A market runs. Use --Profile uk_paper only."
}

$burninScript = Join-Path (Split-Path -Parent $PSCommandPath) "run_step1a_burnin_auto_client.ps1"
if (-not (Test-Path $burninScript)) {
    throw "Burn-in script not found: $burninScript"
}

$invokeParams = @{
    Profile = $Profile
    Runs = $Runs
    PaperDurationSeconds = $PaperDurationSeconds
    MinFilledOrders = $MinFilledOrders
    MinSymbolDataAvailabilityRatio = $MinSymbolDataAvailabilityRatio
    PreflightMinBarsPerSymbol = $PreflightMinBarsPerSymbol
    PreflightPeriod = $PreflightPeriod
    PreflightInterval = $PreflightInterval
    SkipSymbolAvailabilityPreflight = [bool]$SkipSymbolAvailabilityPreflight
    AppendBacklogEvidence = [bool]$AppendBacklogEvidence
    ClearKillSwitchBeforeEachRun = [bool]$ClearKillSwitchBeforeEachRun
}

& $burninScript @invokeParams

exit $LASTEXITCODE
