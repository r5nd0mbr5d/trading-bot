param(
    [string]$Profile = "uk_paper",
    [int]$Runs = 3,
    [int]$PaperDurationSeconds = 1800,
    [int]$MinFilledOrders = 5,
    [switch]$AppendBacklogEvidence,
    [switch]$ClearKillSwitchBeforeEachRun
)

$ErrorActionPreference = "Stop"

$burninScript = Join-Path (Split-Path -Parent $PSCommandPath) "run_step1a_burnin.ps1"
if (-not (Test-Path $burninScript)) {
    throw "Burn-in script not found: $burninScript"
}

$invokeParams = @{
    Profile = $Profile
    Runs = $Runs
    PaperDurationSeconds = $PaperDurationSeconds
    MinFilledOrders = $MinFilledOrders
    AppendBacklogEvidence = [bool]$AppendBacklogEvidence
    ClearKillSwitchBeforeEachRun = [bool]$ClearKillSwitchBeforeEachRun
}

& $burninScript @invokeParams

exit $LASTEXITCODE
