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

$scriptPath = Join-Path $PSScriptRoot "scripts\run_step1a_market_if_window.ps1"
if (-not (Test-Path $scriptPath)) {
    throw "Script not found: $scriptPath"
}

$invokeParams = @{
    Profile = $Profile
    Runs = $Runs
    PaperDurationSeconds = $PaperDurationSeconds
    MinFilledOrders = $MinFilledOrders
    AppendBacklogEvidence = [bool]$AppendBacklogEvidence
    ClearKillSwitchBeforeEachRun = [bool]$ClearKillSwitchBeforeEachRun
    WindowStartUtcHour = $WindowStartUtcHour
    WindowEndUtcHour = $WindowEndUtcHour
}

& $scriptPath @invokeParams

exit $LASTEXITCODE
