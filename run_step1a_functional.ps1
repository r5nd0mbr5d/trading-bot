param(
    [string]$Profile = "uk_paper",
    [int]$PaperDurationSeconds = 180,
    [int]$FunctionalFailureLimit = 9999,
    [switch]$AppendBacklogEvidence,
    [switch]$ClearKillSwitchBeforeEachRun
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "scripts\run_step1a_functional.ps1"
if (-not (Test-Path $scriptPath)) {
    throw "Script not found: $scriptPath"
}

$invokeParams = @{
    Profile = $Profile
    PaperDurationSeconds = $PaperDurationSeconds
    FunctionalFailureLimit = $FunctionalFailureLimit
    AppendBacklogEvidence = [bool]$AppendBacklogEvidence
    ClearKillSwitchBeforeEachRun = [bool]$ClearKillSwitchBeforeEachRun
}

& $scriptPath @invokeParams

exit $LASTEXITCODE
