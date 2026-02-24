param(
    [string]$Profile = "uk_paper",
    [int]$Runs = 3,
    [int]$PaperDurationSeconds = 1800,
    [int]$MinFilledOrders = 5,
    [switch]$AppendBacklogEvidence,
    [switch]$ClearKillSwitchBeforeEachRun
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "scripts\run_step1a_market.ps1"
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
}

& $scriptPath @invokeParams

exit $LASTEXITCODE
