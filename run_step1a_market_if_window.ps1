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
    [switch]$ClearKillSwitchBeforeEachRun,
    [int]$WindowStartUtcHour = 8,
    [int]$WindowEndUtcHour = 16
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "scripts\run_step1a_market_if_window.ps1"
if (-not (Test-Path $scriptPath)) {
    throw "Script not found: $scriptPath"
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
    WindowStartUtcHour = $WindowStartUtcHour
    WindowEndUtcHour = $WindowEndUtcHour
}

& $scriptPath @invokeParams

exit $LASTEXITCODE
