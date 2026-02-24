param(
    [string]$Profile = "uk_paper",
    [int]$Runs = 3,
    [int]$PaperDurationSeconds = 1800,
    [int]$MinFilledOrders = 5,
    [string]$OutputRoot = "reports/uk_tax/step1a_burnin",
    [switch]$AppendBacklogEvidence,
    [string]$BacklogPath = "IMPLEMENTATION_BACKLOG.md",
    [switch]$AllowOutsideWindow,
    [switch]$ClearKillSwitchBeforeEachRun
)

$ErrorActionPreference = "Stop"

function Get-UtcNow {
    return (Get-Date).ToUniversalTime()
}

function Test-InWindow {
    param([datetime]$UtcDateTime)
    $hour = $UtcDateTime.Hour
    return ($hour -ge 8 -and $hour -lt 16)
}

function Invoke-StepCommand {
    param(
        [string]$Label,
        [string[]]$Args,
        [string]$LogPath
    )

    Write-Host "`n[$Label] python $($Args -join ' ')"
    & python @Args 2>&1 | Tee-Object -FilePath $LogPath
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        throw "$Label failed with exit code $exitCode (see $LogPath)"
    }
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

function Export-BrokerSnapshot {
    param(
        [string]$ProfileName,
        [string]$SnapshotPath
    )

    $snapshotCode = @'
import json
import sys
from config.settings import Settings
from main import apply_runtime_profile
from src.execution.ibkr_broker import IBKRBroker

path = sys.argv[1]
profile = sys.argv[2]
payload = {
    "ok": False,
    "profile": profile,
    "account": "",
    "is_paper_account": False,
    "base_currency": "",
    "cash": 0.0,
    "portfolio_value": 0.0,
    "error": "",
}

broker = None
try:
    settings = Settings()
    apply_runtime_profile(settings, profile)
    broker = IBKRBroker(settings)
    payload["account"] = broker.get_primary_account()
    payload["is_paper_account"] = broker.is_paper_account()
    payload["base_currency"] = broker.get_account_base_currency()
    payload["cash"] = float(broker.get_cash())
    payload["portfolio_value"] = float(broker.get_portfolio_value())
    payload["ok"] = True
except Exception as exc:
    payload["error"] = str(exc)
finally:
    try:
        if broker is not None:
            broker.disconnect()
    except Exception:
        pass

with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
'@

    python -c $snapshotCode $SnapshotPath $ProfileName
    if ($LASTEXITCODE -ne 0) {
        throw "Broker snapshot export failed (see $SnapshotPath)"
    }
}

if ($Runs -lt 1) {
    throw "Runs must be >= 1"
}

$sessionUtc = Get-UtcNow
$sessionId = $sessionUtc.ToString("yyyyMMdd_HHmmss")
$sessionDir = Join-Path $OutputRoot "session_$sessionId"
New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null

Write-Host "Step 1A burn-in session: $sessionId"
Write-Host "Output directory: $sessionDir"
Write-Host "Required window: 08:00-16:00 UTC"

$runResults = @()
$allPassed = $true

for ($runIndex = 1; $runIndex -le $Runs; $runIndex++) {
    $runStartUtc = Get-UtcNow
    $windowOk = Test-InWindow -UtcDateTime $runStartUtc
    $runId = "run_$runIndex"
    $runDir = Join-Path $sessionDir $runId
    New-Item -ItemType Directory -Path $runDir -Force | Out-Null

    Write-Host "`n===== Step 1A Burn-In Run $runIndex/$Runs ====="
    Write-Host "UTC start: $($runStartUtc.ToString("yyyy-MM-dd HH:mm:ss"))"
    Write-Host "In-window: $windowOk"

    if (-not $windowOk -and -not $AllowOutsideWindow) {
        $result = [PSCustomObject]@{
            run = $runIndex
            utc_start = $runStartUtc.ToString("o")
            in_window = $false
            passed = $false
            reason = "outside_allowed_window"
            run_dir = $runDir
        }
        $runResults += $result
        $allPassed = $false
        break
    }

    $healthLog = Join-Path $runDir "01_health_check.log"
    $trialLog = Join-Path $runDir "02_paper_trial.log"
    $summaryLog = Join-Path $runDir "03_session_summary.log"
    $taxLog = Join-Path $runDir "04_tax_export.log"
    $reconcileLog = Join-Path $runDir "05_reconcile.log"

    $summaryPath = Join-Path $runDir "paper_session_summary.json"
    $reconcilePath = Join-Path $runDir "paper_reconciliation.json"
    $tradeLedgerPath = Join-Path $runDir "trade_ledger.csv"
    $realizedGainsPath = Join-Path $runDir "realized_gains.csv"
    $fxNotesPath = Join-Path $runDir "fx_notes.csv"

    $snapshotPrePath = Join-Path $runDir "broker_snapshot_pre.json"
    $snapshotPostPath = Join-Path $runDir "broker_snapshot_post.json"

    $runPassed = $false
    $failureReason = ""

    try {
        if ($ClearKillSwitchBeforeEachRun) {
            python -c "import sqlite3; db = sqlite3.connect('trading_paper.db'); db.execute('DELETE FROM kill_switch'); db.commit(); print('Kill switch cleared')"
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to clear kill_switch table"
            }
        }

        Export-BrokerSnapshot -ProfileName $Profile -SnapshotPath $snapshotPrePath

        Invoke-StepCommand -Label "1/5 Health check" -LogPath $healthLog -Args @(
            "main.py", "uk_health_check", "--profile", $Profile, "--strict-health"
        )

        Invoke-StepCommand -Label "2/5 Paper trial" -LogPath $trialLog -Args @(
            "main.py",
            "paper_trial",
            "--confirm-paper-trial",
            "--profile",
            $Profile,
            "--paper-duration-seconds",
            "$PaperDurationSeconds",
            "--skip-rotate"
        )

        Invoke-StepCommand -Label "3/5 Paper session summary" -LogPath $summaryLog -Args @(
            "main.py", "paper_session_summary", "--profile", $Profile, "--output-dir", $runDir
        )

        Invoke-StepCommand -Label "4/5 UK tax export" -LogPath $taxLog -Args @(
            "main.py", "uk_tax_export", "--profile", $Profile, "--output-dir", $runDir
        )

        Invoke-StepCommand -Label "5/5 Strict reconcile" -LogPath $reconcileLog -Args @(
            "main.py",
            "paper_reconcile",
            "--profile",
            $Profile,
            "--output-dir",
            $runDir,
            "--expected-json",
            $summaryPath,
            "--strict-reconcile"
        )

        Export-BrokerSnapshot -ProfileName $Profile -SnapshotPath $snapshotPostPath

        $summary = Get-Content -Path $summaryPath -Raw | ConvertFrom-Json
        $reconcile = Get-Content -Path $reconcilePath -Raw | ConvertFrom-Json
        $snapshotPre = Get-Content -Path $snapshotPrePath -Raw | ConvertFrom-Json
        $snapshotPost = Get-Content -Path $snapshotPostPath -Raw | ConvertFrom-Json

        $filledOrderCount = [int]$summary.filled_order_count
        $driftFlagCount = [int]$reconcile.report.drift_flag_count

        $artifactChecks = [ordered]@{
            paper_session_summary_json = (Test-Path $summaryPath)
            paper_reconciliation_json = (Test-Path $reconcilePath)
            trade_ledger_csv = (Test-Path $tradeLedgerPath)
            realized_gains_csv = (Test-Path $realizedGainsPath)
            fx_notes_csv = (Test-Path $fxNotesPath)
        }
        $allArtifactsPresent = $true
        foreach ($present in $artifactChecks.Values) {
            if (-not $present) {
                $allArtifactsPresent = $false
                break
            }
        }

        $eventLoopErrorSeen = Select-String -Path $trialLog -Pattern "This event loop is already running" -SimpleMatch -Quiet
        $clientIdErrorSeen = Select-String -Path $trialLog -Pattern "client id is already in use" -SimpleMatch -Quiet

        $preSnapshotNonZero = ($snapshotPre.ok -eq $true -and [double]$snapshotPre.cash -gt 0 -and [double]$snapshotPre.portfolio_value -gt 0)
        $postSnapshotNonZero = ($snapshotPost.ok -eq $true -and [double]$snapshotPost.cash -gt 0 -and [double]$snapshotPost.portfolio_value -gt 0)

        $gateFilled = ($filledOrderCount -ge $MinFilledOrders)
        $gateDrift = ($driftFlagCount -eq 0)
        $gateNoLoopError = (-not $eventLoopErrorSeen)
        $gateNoClientIdError = (-not $clientIdErrorSeen)
        $gateSnapshots = ($preSnapshotNonZero -and $postSnapshotNonZero)

        $runPassed = ($windowOk -and $allArtifactsPresent -and $gateFilled -and $gateDrift -and $gateNoLoopError -and $gateNoClientIdError -and $gateSnapshots)

        if (-not $runPassed) {
            $failureReason = "criteria_not_met"
        }

        $result = [PSCustomObject]@{
            run = $runIndex
            utc_start = $runStartUtc.ToString("o")
            in_window = $windowOk
            commands_passed = $true
            filled_order_count = $filledOrderCount
            min_filled_orders_required = $MinFilledOrders
            drift_flag_count = $driftFlagCount
            event_loop_error_seen = $eventLoopErrorSeen
            client_id_in_use_error_seen = $clientIdErrorSeen
            broker_snapshot_pre = $snapshotPre
            broker_snapshot_post = $snapshotPost
            broker_snapshot_nonzero_ok = $gateSnapshots
            artifacts = $artifactChecks
            all_artifacts_present = $allArtifactsPresent
            passed = $runPassed
            reason = $failureReason
            run_dir = $runDir
            logs = [ordered]@{
                health_check = $healthLog
                paper_trial = $trialLog
                paper_session_summary = $summaryLog
                uk_tax_export = $taxLog
                paper_reconcile = $reconcileLog
            }
        }
        $runResults += $result
    }
    catch {
        $allPassed = $false
        $result = [PSCustomObject]@{
            run = $runIndex
            utc_start = $runStartUtc.ToString("o")
            in_window = $windowOk
            commands_passed = $false
            passed = $false
            reason = "command_failed"
            error = $_.Exception.Message
            run_dir = $runDir
            logs = [ordered]@{
                health_check = $healthLog
                paper_trial = $trialLog
                paper_session_summary = $summaryLog
                uk_tax_export = $taxLog
                paper_reconcile = $reconcileLog
            }
        }
        $runResults += $result
        break
    }

    if (-not $runPassed) {
        $allPassed = $false
        break
    }
}

$completedRuns = $runResults.Count
$passedRuns = ($runResults | Where-Object { $_.passed -eq $true }).Count
$sessionPassed = ($allPassed -and $completedRuns -eq $Runs -and $passedRuns -eq $Runs)

$report = [ordered]@{
    step = "1A"
    profile = $Profile
    generated_at_utc = (Get-UtcNow).ToString("o")
    required_window_utc = "08:00-16:00"
    runs_required = $Runs
    runs_completed = $completedRuns
    runs_passed = $passedRuns
    paper_duration_seconds = $PaperDurationSeconds
    min_filled_orders_required = $MinFilledOrders
    session_passed = $sessionPassed
    signoff_ready = $sessionPassed
    output_dir = $sessionDir
    run_results = $runResults
}

$reportPath = Join-Path $sessionDir "step1a_burnin_report.json"
$latestPath = Join-Path $OutputRoot "step1a_burnin_latest.json"
Write-JsonFile -Path $reportPath -Payload $report
Write-JsonFile -Path $latestPath -Payload $report

if ($AppendBacklogEvidence) {
    $appendScript = Join-Path (Split-Path -Parent $PSCommandPath) "append_step1a_evidence.ps1"
    if (-not (Test-Path $appendScript)) {
        throw "Append evidence script not found: $appendScript"
    }
    & $appendScript -ReportPath $latestPath -BacklogPath $BacklogPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to append Step 1A evidence to backlog"
    }
}

Write-Host "`nStep 1A burn-in report written: $reportPath"
Write-Host "Latest report pointer: $latestPath"
Write-Host "Runs passed: $passedRuns / $Runs"

if ($sessionPassed) {
    Write-Host "SIGN-OFF STATUS: READY"
    exit 0
}

Write-Host "SIGN-OFF STATUS: NOT READY"
exit 1
