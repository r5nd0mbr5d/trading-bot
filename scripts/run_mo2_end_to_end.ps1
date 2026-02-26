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

    $host = $env:IBKR_HOST
    if ([string]::IsNullOrWhiteSpace($host)) {
        $host = "127.0.0.1"
    }

    $port = $env:IBKR_PORT
    if ([string]::IsNullOrWhiteSpace($port)) {
        if ($ProfileName -eq "uk_paper") {
            $port = "7497"
        }
        else {
            $port = "7496"
        }
    }

    $mode = "custom"
    if ($port -eq "7497") {
        $mode = "paper"
    }
    elseif ($port -eq "7496") {
        $mode = "live"
    }

    return "ibkr:{0}:{1}:{2}:{3}" -f $ProfileName, $mode, $host, $port
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
        append_backlog_evidence = [bool]$AppendBacklogEvidence
    }
    execution = [ordered]@{
        exit_code = $exitCode
        passed = ($exitCode -eq 0)
        log_path = $logPath
        latest_burnin_report = $latestBurnInReport
        latest_burnin_report_exists = (Test-Path $latestBurnInReport)
    }
}

$reportPath = Join-Path $sessionDir "mo2_orchestrator_report.json"
Write-JsonFile -Path $reportPath -Payload $orchestratorReport

Write-Host "MO-2 orchestration end (UTC): $($endUtc.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Host "Duration (s): $durationSeconds"
Write-Host "Log: $logPath"
Write-Host "Report: $reportPath"

if ($exitCode -eq 0) {
    Write-Host "MO-2 STATUS: PASSED"
}
else {
    Write-Host "MO-2 STATUS: FAILED (exit=$exitCode)"
}

exit $exitCode
