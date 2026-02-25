param(
    [string]$Profile = "uk_paper",
    [int]$Runs = 3,
    [int]$PaperDurationSeconds = 1800,
    [int]$FunctionalDurationSeconds = 180,
    [int]$MinFilledOrders = 5,
    [double]$MinSymbolDataAvailabilityRatio = 0.80,
    [int]$PreflightMinBarsPerSymbol = 100,
    [string]$PreflightPeriod = "5d",
    [string]$PreflightInterval = "1m",
    [switch]$SkipSymbolAvailabilityPreflight,
    [string]$OutputRoot = "reports/uk_tax/step1a_burnin",
    [switch]$AppendBacklogEvidence,
    [string]$BacklogPath = "IMPLEMENTATION_BACKLOG.md",
    [switch]$AllowOutsideWindow,
    [switch]$NonQualifyingTestMode,
    [switch]$ClearKillSwitchBeforeEachRun,
    [int]$InitialClientId = 70,
    [int]$MaxClientIdAttempts = 8,
    [int]$ClientIdStep = 1,
    [string]$LatestReportPath = "reports/uk_tax/step1a_burnin/step1a_burnin_latest.json"
)

$ErrorActionPreference = "Stop"

if ($Profile -ne "uk_paper") {
    throw "Profile '$Profile' is not allowed for Step 1A burn-in runs. Use --Profile uk_paper only."
}

if ($MaxClientIdAttempts -lt 1) {
    throw "MaxClientIdAttempts must be >= 1"
}

if ($ClientIdStep -lt 1) {
    throw "ClientIdStep must be >= 1"
}

$burninScript = Join-Path (Split-Path -Parent $PSCommandPath) "run_step1a_burnin.ps1"
if (-not (Test-Path $burninScript)) {
    throw "Burn-in script not found: $burninScript"
}

function Test-ClientIdCollisionFromReport {
    param(
        [string]$ReportPath
    )

    if (-not (Test-Path $ReportPath)) {
        return $false
    }

    try {
        $report = Get-Content -Path $ReportPath -Raw | ConvertFrom-Json
        if ($null -eq $report.run_results) {
            return $false
        }

        foreach ($result in $report.run_results) {
            if ($null -ne $result.client_id_in_use_error_seen -and $result.client_id_in_use_error_seen -eq $true) {
                return $true
            }
        }
    }
    catch {
        return $false
    }

    return $false
}

$originalClientId = $env:IBKR_CLIENT_ID
$lastExitCode = 1

try {
    for ($attempt = 0; $attempt -lt $MaxClientIdAttempts; $attempt++) {
        $candidateClientId = $InitialClientId + ($attempt * $ClientIdStep)
        $env:IBKR_CLIENT_ID = "$candidateClientId"

        Write-Host "[Step1A AutoClient] Attempt $($attempt + 1)/$MaxClientIdAttempts using IBKR_CLIENT_ID=$candidateClientId"

        $invokeParams = @{
            Profile = $Profile
            Runs = $Runs
            PaperDurationSeconds = $PaperDurationSeconds
            FunctionalDurationSeconds = $FunctionalDurationSeconds
            MinFilledOrders = $MinFilledOrders
            MinSymbolDataAvailabilityRatio = $MinSymbolDataAvailabilityRatio
            PreflightMinBarsPerSymbol = $PreflightMinBarsPerSymbol
            PreflightPeriod = $PreflightPeriod
            PreflightInterval = $PreflightInterval
            SkipSymbolAvailabilityPreflight = [bool]$SkipSymbolAvailabilityPreflight
            OutputRoot = $OutputRoot
            AppendBacklogEvidence = [bool]$AppendBacklogEvidence
            BacklogPath = $BacklogPath
            AllowOutsideWindow = [bool]$AllowOutsideWindow
            NonQualifyingTestMode = [bool]$NonQualifyingTestMode
            ClearKillSwitchBeforeEachRun = [bool]$ClearKillSwitchBeforeEachRun
        }

        & $burninScript @invokeParams
        $lastExitCode = $LASTEXITCODE

        if ($lastExitCode -eq 0) {
            Write-Host "[Step1A AutoClient] Success with IBKR_CLIENT_ID=$candidateClientId"
            exit 0
        }

        $clientIdCollision = Test-ClientIdCollisionFromReport -ReportPath $LatestReportPath
        if (-not $clientIdCollision) {
            Write-Host "[Step1A AutoClient] Non-collision failure (exit=$lastExitCode). Stopping retries."
            exit $lastExitCode
        }

        Write-Host "[Step1A AutoClient] Detected client-id collision in report, retrying with next client id..."
    }

    Write-Host "[Step1A AutoClient] Exhausted client-id attempts ($MaxClientIdAttempts)."
    exit $lastExitCode
}
finally {
    if ($null -ne $originalClientId) {
        $env:IBKR_CLIENT_ID = $originalClientId
    }
    else {
        Remove-Item Env:IBKR_CLIENT_ID -ErrorAction SilentlyContinue
    }
}