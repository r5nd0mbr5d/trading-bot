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
    [switch]$ClearKillSwitchBeforeEachRun = $true,
    [string]$OutputRoot = "reports/uk_tax/mo2_orchestrator",
    [int]$WindowStartUtcHour = 8,
    [int]$WindowEndUtcHour = 16
)

$ErrorActionPreference = "Stop"

if ($Profile -ne "uk_paper") {
    throw "Profile '$Profile' is not allowed for MO-2 orchestrator. Use --Profile uk_paper only."
}

if ($Runs -lt 1) {
    throw "Runs must be >= 1"
}

function Get-UtcNow {
    return (Get-Date).ToUniversalTime()
}

function Test-InWindow {
    param([datetime]$UtcDateTime)
    $hour = $UtcDateTime.Hour
    return ($hour -ge $WindowStartUtcHour -and $hour -lt $WindowEndUtcHour)
}

function Get-EndpointProfileTag {
    param([string]$ProfileName)

    $ibkrHost = $env:IBKR_HOST
    if ([string]::IsNullOrWhiteSpace($ibkrHost)) {
        $ibkrHost = "127.0.0.1"
    }

    $ibkrPort = $env:IBKR_PORT
    if ([string]::IsNullOrWhiteSpace($ibkrPort)) {
        if ($ProfileName -eq "uk_paper") {
            $ibkrPort = "7497"
        }
        else {
            $ibkrPort = "7496"
        }
    }

    $mode = "custom"
    if ($ibkrPort -eq "7497") {
        $mode = "paper"
    }
    elseif ($ibkrPort -eq "7496") {
        $mode = "live"
    }

    return "ibkr:{0}:{1}:{2}:{3}" -f $ProfileName, $mode, $ibkrHost, $ibkrPort
}

function Write-JsonFile {
    param(
        [string]$Path,
        [object]$Payload
    )

    $directory = Split-Path -Path $Path -Parent
    if (-not (Test-Path $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $Payload | ConvertTo-Json -Depth 10 | Set-Content -Path $Path -Encoding UTF8
}

function Get-BurnInEvidenceLane {
    param([string]$ReportPath)

    if (-not (Test-Path $ReportPath)) {
        return $null
    }

    try {
        $payload = Get-Content -Path $ReportPath -Raw | ConvertFrom-Json
        return [string]$payload.evidence_lane
    }
    catch {
        return $null
    }
}

$startUtc = Get-UtcNow
$inWindow = Test-InWindow -UtcDateTime $startUtc

if (-not $inWindow) {
    throw (
        "MO-2 orchestrator must start in-window. Current UTC=" +
        $startUtc.ToString("yyyy-MM-dd HH:mm:ss") +
        ", required window=" +
        "$WindowStartUtcHour`:00-$WindowEndUtcHour`:00"
    )
}

$sessionId = $startUtc.ToString("yyyyMMdd_HHmmss")
$sessionDir = Join-Path $OutputRoot "session_$sessionId"
New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null

$logPath = Join-Path $sessionDir "mo2_orchestrator.log"
if (Test-Path $logPath) {
    Remove-Item -Force $logPath
}

$marketScript = Join-Path (Split-Path -Parent $PSCommandPath) "run_step1a_market.ps1"
if (-not (Test-Path $marketScript)) {
    throw "Market runner script not found: $marketScript"
}

$endpointProfileTag = Get-EndpointProfileTag -ProfileName $Profile

Write-Host "MO-2 orchestration start (UTC): $($startUtc.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "Session directory: $sessionDir"
Write-Host "Guardrails: profile=uk_paper, window=${WindowStartUtcHour}:00-${WindowEndUtcHour}:00 UTC"
Write-Host "Endpoint profile tag: $endpointProfileTag"
Write-Host "Run settings: runs=$Runs, paper_duration_seconds=$PaperDurationSeconds, min_filled_orders=$MinFilledOrders"
if (-not $SkipSymbolAvailabilityPreflight) {
    Write-Host "Preflight gate: enabled, min_data_availability_ratio=$MinSymbolDataAvailabilityRatio, min_bars_per_symbol=$PreflightMinBarsPerSymbol, period=$PreflightPeriod, interval=$PreflightInterval"
}
else {
    Write-Host "Preflight gate: disabled"
}

$commandArgs = @(
    $marketScript,
    "-Profile", $Profile,
    "-Runs", "$Runs",
    "-PaperDurationSeconds", "$PaperDurationSeconds",
    "-RunObjectiveProfile", "qualifying",
    "-MinFilledOrders", "$MinFilledOrders",
    "-MinSymbolDataAvailabilityRatio", "$MinSymbolDataAvailabilityRatio",
    "-PreflightMinBarsPerSymbol", "$PreflightMinBarsPerSymbol",
    "-PreflightPeriod", "$PreflightPeriod",
    "-PreflightInterval", "$PreflightInterval"
)
if ($SkipSymbolAvailabilityPreflight) {
    $commandArgs += "-SkipSymbolAvailabilityPreflight"
}
if ($AppendBacklogEvidence) {
    $commandArgs += "-AppendBacklogEvidence"
}
if ($ClearKillSwitchBeforeEachRun) {
    $commandArgs += "-ClearKillSwitchBeforeEachRun"
}

$stderrPath = "$logPath.stderr"
if (Test-Path $stderrPath) {
    Remove-Item -Force $stderrPath
}

$psArgs = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File"
) + $commandArgs

$process = Start-Process -FilePath "powershell" -ArgumentList $psArgs -NoNewWindow -Wait -PassThru -RedirectStandardOutput $logPath -RedirectStandardError $stderrPath

if (Test-Path $stderrPath) {
    Get-Content -Path $stderrPath | Add-Content -Path $logPath
    Remove-Item -Force $stderrPath
}

$endUtc = Get-UtcNow
$durationSeconds = [int][Math]::Round(($endUtc - $startUtc).TotalSeconds)
$exitCode = $process.ExitCode
$latestBurnInReport = "reports/uk_tax/step1a_burnin/step1a_burnin_latest.json"
$observedEvidenceLane = Get-BurnInEvidenceLane -ReportPath $latestBurnInReport
$laneValidated = ($observedEvidenceLane -eq "qualifying")
$effectiveExitCode = $exitCode
if ($effectiveExitCode -eq 0 -and -not $laneValidated) {
    $effectiveExitCode = 1
}

$orchestratorReport = [ordered]@{
    generated_at_utc = $endUtc.ToString("o")
    orchestration_start_utc = $startUtc.ToString("o")
    orchestration_end_utc = $endUtc.ToString("o")
    duration_seconds = $durationSeconds
    session_id = $sessionId
    profile = $Profile
    endpoint_profile_tag = $endpointProfileTag
    required_window_utc = "$WindowStartUtcHour`:00-$WindowEndUtcHour`:00"
    guardrails = [ordered]@{
        profile_locked_to_uk_paper = $true
        in_window_start_required = $true
        clear_kill_switch_before_each_run = [bool]$ClearKillSwitchBeforeEachRun
        min_filled_orders_required = $MinFilledOrders
        symbol_data_preflight_enabled = [bool](-not $SkipSymbolAvailabilityPreflight)
        min_symbol_data_availability_ratio = $MinSymbolDataAvailabilityRatio
        preflight_min_bars_per_symbol = $PreflightMinBarsPerSymbol
        preflight_period = $PreflightPeriod
        preflight_interval = $PreflightInterval
    }
    command = [ordered]@{
        script = $marketScript
        runs = $Runs
        paper_duration_seconds = $PaperDurationSeconds
        run_objective_profile = "qualifying"
        append_backlog_evidence = [bool]$AppendBacklogEvidence
    }
    execution = [ordered]@{
        exit_code = $effectiveExitCode
        passed = ($effectiveExitCode -eq 0)
        log_path = $logPath
        latest_burnin_report = $latestBurnInReport
        latest_burnin_report_exists = (Test-Path $latestBurnInReport)
        expected_evidence_lane = "qualifying"
        observed_evidence_lane = $observedEvidenceLane
        evidence_lane_validated = $laneValidated
    }
}

$reportPath = Join-Path $sessionDir "mo2_orchestrator_report.json"
Write-JsonFile -Path $reportPath -Payload $orchestratorReport

Write-Host "MO-2 orchestration end (UTC): $($endUtc.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "Duration (s): $durationSeconds"
Write-Host "Log: $logPath"
Write-Host "Report: $reportPath"

if ($effectiveExitCode -eq 0) {
    Write-Host "MO-2 STATUS: PASSED"
}
else {
    Write-Host "MO-2 STATUS: FAILED (exit=$effectiveExitCode)"
}

exit $effectiveExitCode
