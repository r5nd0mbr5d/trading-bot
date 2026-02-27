param(
    [string]$Profile = "uk_paper",
    [int]$PaperDurationSeconds = 180,
    [ValidateSet("smoke", "orchestration", "reconcile")]
    [string]$RunObjectiveProfile = "orchestration",
    [int]$FunctionalFailureLimit = 9999,
    [switch]$AppendBacklogEvidence,
    [switch]$ClearKillSwitchBeforeEachRun
)

$ErrorActionPreference = "Stop"

if ($Profile -ne "uk_paper") {
    throw "Profile '$Profile' is not allowed for Step 1A functional runs. Use --Profile uk_paper only."
}

$burninScript = Join-Path (Split-Path -Parent $PSCommandPath) "run_step1a_burnin.ps1"
if (-not (Test-Path $burninScript)) {
    throw "Burn-in script not found: $burninScript"
}

$invokeParams = @{
    Profile = $Profile
    Runs = 1
    PaperDurationSeconds = $PaperDurationSeconds
    RunObjectiveProfile = $RunObjectiveProfile
    NonQualifyingTestMode = $true
    AppendBacklogEvidence = [bool]$AppendBacklogEvidence
    ClearKillSwitchBeforeEachRun = [bool]$ClearKillSwitchBeforeEachRun
}

$previousFailureLimit = $env:BROKER_OUTAGE_CONSECUTIVE_FAILURE_LIMIT
$env:BROKER_OUTAGE_CONSECUTIVE_FAILURE_LIMIT = "$FunctionalFailureLimit"
try {
    & $burninScript @invokeParams
}
finally {
    if ($null -eq $previousFailureLimit) {
        Remove-Item Env:BROKER_OUTAGE_CONSECUTIVE_FAILURE_LIMIT -ErrorAction SilentlyContinue
    }
    else {
        $env:BROKER_OUTAGE_CONSECUTIVE_FAILURE_LIMIT = $previousFailureLimit
    }
}

exit $LASTEXITCODE
