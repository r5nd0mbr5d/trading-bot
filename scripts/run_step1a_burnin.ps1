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
    [switch]$ClearKillSwitchBeforeEachRun
)

$ErrorActionPreference = "Stop"

if ($Profile -ne "uk_paper") {
    throw "Profile '$Profile' is not allowed for Step 1A burn-in runs. Use --Profile uk_paper only."
}

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
        [string[]]$CommandArgs,
        [string]$LogPath
    )

    Write-Host "`n[$Label] python $($CommandArgs -join ' ')"

    $stderrPath = "$LogPath.stderr"
    if (Test-Path $LogPath) {
        Remove-Item -Force $LogPath
    }
    if (Test-Path $stderrPath) {
        Remove-Item -Force $stderrPath
    }

    $startParams = @{
        FilePath = "python"
        ArgumentList = $CommandArgs
        NoNewWindow = $true
        Wait = $true
        PassThru = $true
        RedirectStandardOutput = $LogPath
        RedirectStandardError = $stderrPath
    }
    $process = Start-Process @startParams

    if (Test-Path $stderrPath) {
        Get-Content -Path $stderrPath | Add-Content -Path $LogPath
        Remove-Item -Force $stderrPath
    }

    if (Test-Path $LogPath) {
        Get-Content -Path $LogPath
    }

    $exitCode = $process.ExitCode

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

function Invoke-SymbolDataPreflight {
    param(
        [string]$ProfileName,
        [string]$ReportPath,
        [string]$Period,
        [string]$Interval,
        [int]$MinBarsPerSymbol
    )

    $preflightCode = @'
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from config.settings import Settings
from src.cli.runtime import apply_runtime_profile
from src.data.feeds import MarketDataFeed

path = sys.argv[1]
profile = sys.argv[2]
period = sys.argv[3]
interval = sys.argv[4]
min_bars = int(sys.argv[5])

payload = {
    "ok": False,
    "profile": profile,
    "period": period,
    "interval": interval,
    "min_bars_per_symbol": min_bars,
    "symbols": [],
    "summary": {
        "total_symbols": 0,
        "available_symbols": 0,
        "availability_ratio": 0.0,
    },
    "error": "",
}

try:
    settings = Settings()
    apply_runtime_profile(settings, profile)
    feed = MarketDataFeed(settings)

    symbols = list(settings.data.symbols)
    payload["summary"]["total_symbols"] = len(symbols)
    available_symbols = 0

    for symbol in symbols:
        entry = {
            "symbol": symbol,
            "bars": 0,
            "available": False,
            "error": "",
        }
        try:
            frame = feed.fetch_historical(symbol, period=period, interval=interval)
            bars = len(frame)
            entry["bars"] = bars
            entry["available"] = bars >= min_bars
            if bars < min_bars:
                entry["error"] = f"insufficient_bars:{bars}"
        except Exception as exc:
            entry["error"] = str(exc)

        if entry["available"]:
            available_symbols += 1

        payload["symbols"].append(entry)

    total_symbols = payload["summary"]["total_symbols"]
    ratio = 0.0
    if total_symbols > 0:
        ratio = available_symbols / total_symbols

    payload["summary"]["available_symbols"] = available_symbols
    payload["summary"]["availability_ratio"] = ratio
    payload["ok"] = True
except Exception as exc:
    payload["error"] = str(exc)

with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
'@

    $tempPy = [System.IO.Path]::Combine(
        [System.IO.Path]::GetTempPath(),
        "step1a_symbol_preflight_" + [System.Guid]::NewGuid().ToString("N") + ".py"
    )
    Set-Content -Path $tempPy -Value $preflightCode -Encoding UTF8
    try {
        & python $tempPy $ReportPath $ProfileName $Period $Interval "$MinBarsPerSymbol"
        if ($LASTEXITCODE -ne 0) {
            throw "Symbol data preflight command failed (see $ReportPath)"
        }
    }
    finally {
        if (Test-Path $tempPy) {
            Remove-Item -Force $tempPy
        }
    }
}

function Export-BrokerSnapshot {
    param(
        [string]$ProfileName,
        [string]$SnapshotPath
    )

    $snapshotCode = @'
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

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

    $tempPy = [System.IO.Path]::Combine(
        [System.IO.Path]::GetTempPath(),
        "step1a_snapshot_" + [System.Guid]::NewGuid().ToString("N") + ".py"
    )
    Set-Content -Path $tempPy -Value $snapshotCode -Encoding UTF8
    try {
        & python $tempPy $SnapshotPath $ProfileName
        if ($LASTEXITCODE -ne 0) {
            throw "Broker snapshot export failed (see $SnapshotPath)"
        }
    }
    finally {
        if (Test-Path $tempPy) {
            Remove-Item -Force $tempPy
        }
    }
}

if ($Runs -lt 1) {
    throw "Runs must be >= 1"
}

if ($FunctionalDurationSeconds -lt 30) {
    throw "FunctionalDurationSeconds must be >= 30"
}

if ($MinSymbolDataAvailabilityRatio -lt 0.0 -or $MinSymbolDataAvailabilityRatio -gt 1.0) {
    throw "MinSymbolDataAvailabilityRatio must be in [0.0, 1.0]"
}

if ($PreflightMinBarsPerSymbol -lt 1) {
    throw "PreflightMinBarsPerSymbol must be >= 1"
}

$effectivePaperDurationSeconds = $PaperDurationSeconds
if ($NonQualifyingTestMode -and -not $PSBoundParameters.ContainsKey("PaperDurationSeconds")) {
    $effectivePaperDurationSeconds = $FunctionalDurationSeconds
}

$sessionUtc = Get-UtcNow
$sessionId = $sessionUtc.ToString("yyyyMMdd_HHmmss")
$sessionDir = Join-Path $OutputRoot "session_$sessionId"
New-Item -ItemType Directory -Path $sessionDir -Force | Out-Null

Write-Host "Step 1A burn-in session: $sessionId"
Write-Host "Output directory: $sessionDir"
Write-Host "Required window: 08:00-16:00 UTC"
if ($NonQualifyingTestMode) {
    Write-Host "Mode: NON-QUALIFYING TEST (window gate bypassed; sign-off remains false)"
    Write-Host "Effective duration (seconds): $effectivePaperDurationSeconds"
}

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

    if (-not $windowOk -and -not $AllowOutsideWindow -and -not $NonQualifyingTestMode) {
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
    $symbolPreflightPath = Join-Path $runDir "00_symbol_data_preflight.json"

    $runPassed = $false
    $failureReason = ""
    $preflightPayload = $null
    $preflightGatePassed = $true

    try {
        if (-not $SkipSymbolAvailabilityPreflight) {
            Invoke-SymbolDataPreflight -ProfileName $Profile -ReportPath $symbolPreflightPath -Period $PreflightPeriod -Interval $PreflightInterval -MinBarsPerSymbol $PreflightMinBarsPerSymbol
            $preflightPayload = Get-Content -Path $symbolPreflightPath -Raw | ConvertFrom-Json

            if ($preflightPayload.ok -ne $true) {
                throw "Symbol data preflight failed: $($preflightPayload.error)"
            }

            $availabilityRatio = [double]$preflightPayload.summary.availability_ratio
            $preflightGatePassed = ($availabilityRatio -ge $MinSymbolDataAvailabilityRatio)
            if (-not $preflightGatePassed) {
                $result = [PSCustomObject]@{
                    run = $runIndex
                    utc_start = $runStartUtc.ToString("o")
                    in_window = $windowOk
                    commands_passed = $false
                    preflight_gate_passed = $false
                    preflight_gate_threshold_ratio = $MinSymbolDataAvailabilityRatio
                    preflight_data_availability_ratio = $availabilityRatio
                    preflight_report_path = $symbolPreflightPath
                    passed = $false
                    reason = "symbol_data_preflight_failed"
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
                $allPassed = $false
                break
            }
        }

        if ($ClearKillSwitchBeforeEachRun) {
            python -c "import sqlite3; db = sqlite3.connect('trading_paper.db'); db.execute('DELETE FROM kill_switch'); db.commit(); print('Kill switch cleared')"
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to clear kill_switch table"
            }
        }

        Export-BrokerSnapshot -ProfileName $Profile -SnapshotPath $snapshotPrePath

        Invoke-StepCommand -Label "1/5 Health check" -LogPath $healthLog -CommandArgs @(
            "main.py", "uk_health_check", "--profile", $Profile, "--strict-health"
        )

        $originalSymbolRatioEnv = $env:SYMBOL_UNIVERSE_MIN_AVAILABILITY_RATIO
        $originalSymbolMinBarsEnv = $env:SYMBOL_UNIVERSE_MIN_BARS_PER_SYMBOL
        $originalSymbolPeriodEnv = $env:SYMBOL_UNIVERSE_PREFLIGHT_PERIOD
        $originalSymbolIntervalEnv = $env:SYMBOL_UNIVERSE_PREFLIGHT_INTERVAL
        try {
            $env:SYMBOL_UNIVERSE_MIN_AVAILABILITY_RATIO = [string]$MinSymbolDataAvailabilityRatio
            $env:SYMBOL_UNIVERSE_MIN_BARS_PER_SYMBOL = [string]$PreflightMinBarsPerSymbol
            $env:SYMBOL_UNIVERSE_PREFLIGHT_PERIOD = $PreflightPeriod
            $env:SYMBOL_UNIVERSE_PREFLIGHT_INTERVAL = $PreflightInterval

            Invoke-StepCommand -Label "2/5 Paper trial" -LogPath $trialLog -CommandArgs @(
                "main.py",
                "paper_trial",
                "--confirm-paper-trial",
                "--profile",
                $Profile,
                "--paper-duration-seconds",
                "$effectivePaperDurationSeconds",
                "--skip-rotate"
            )
        }
        finally {
            if ($null -ne $originalSymbolRatioEnv) {
                $env:SYMBOL_UNIVERSE_MIN_AVAILABILITY_RATIO = $originalSymbolRatioEnv
            }
            else {
                Remove-Item Env:SYMBOL_UNIVERSE_MIN_AVAILABILITY_RATIO -ErrorAction SilentlyContinue
            }

            if ($null -ne $originalSymbolMinBarsEnv) {
                $env:SYMBOL_UNIVERSE_MIN_BARS_PER_SYMBOL = $originalSymbolMinBarsEnv
            }
            else {
                Remove-Item Env:SYMBOL_UNIVERSE_MIN_BARS_PER_SYMBOL -ErrorAction SilentlyContinue
            }

            if ($null -ne $originalSymbolPeriodEnv) {
                $env:SYMBOL_UNIVERSE_PREFLIGHT_PERIOD = $originalSymbolPeriodEnv
            }
            else {
                Remove-Item Env:SYMBOL_UNIVERSE_PREFLIGHT_PERIOD -ErrorAction SilentlyContinue
            }

            if ($null -ne $originalSymbolIntervalEnv) {
                $env:SYMBOL_UNIVERSE_PREFLIGHT_INTERVAL = $originalSymbolIntervalEnv
            }
            else {
                Remove-Item Env:SYMBOL_UNIVERSE_PREFLIGHT_INTERVAL -ErrorAction SilentlyContinue
            }
        }

        Invoke-StepCommand -Label "3/5 Paper session summary" -LogPath $summaryLog -CommandArgs @(
            "main.py", "paper_session_summary", "--profile", $Profile, "--output-dir", $runDir
        )

        Invoke-StepCommand -Label "4/5 UK tax export" -LogPath $taxLog -CommandArgs @(
            "main.py", "uk_tax_export", "--profile", $Profile, "--output-dir", $runDir
        )

        Invoke-StepCommand -Label "5/5 Strict reconcile" -LogPath $reconcileLog -CommandArgs @(
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

        $preSnapshotConnected = ($snapshotPre.ok -eq $true)
        $postSnapshotConnected = ($snapshotPost.ok -eq $true)
        $preSnapshotNonZero = ($snapshotPre.ok -eq $true -and [double]$snapshotPre.cash -gt 0 -and [double]$snapshotPre.portfolio_value -gt 0)
        $postSnapshotNonZero = ($snapshotPost.ok -eq $true -and [double]$snapshotPost.cash -gt 0 -and [double]$snapshotPost.portfolio_value -gt 0)

        $effectiveMinFilledOrders = $MinFilledOrders
        if ($NonQualifyingTestMode) {
            $effectiveMinFilledOrders = 0
        }

        $gateFilled = ($filledOrderCount -ge $effectiveMinFilledOrders)
        $gateDrift = ($driftFlagCount -eq 0)
        $gateNoLoopError = (-not $eventLoopErrorSeen)
        $gateNoClientIdError = (-not $clientIdErrorSeen)
        $gateSnapshots = ($preSnapshotNonZero -and $postSnapshotNonZero)
        if ($NonQualifyingTestMode) {
            $gateSnapshots = ($preSnapshotConnected -and $postSnapshotConnected)
        }

        $windowGateForRun = $windowOk
        if ($NonQualifyingTestMode) {
            $windowGateForRun = $true
        }

        $runPassed = ($windowGateForRun -and $allArtifactsPresent -and $gateFilled -and $gateDrift -and $gateNoLoopError -and $gateNoClientIdError -and $gateSnapshots)

        if (-not $runPassed) {
            $failureReason = "criteria_not_met"
        }

        $result = [PSCustomObject]@{
            run = $runIndex
            utc_start = $runStartUtc.ToString("o")
            in_window = $windowOk
            commands_passed = $true
            filled_order_count = $filledOrderCount
            min_filled_orders_required = $effectiveMinFilledOrders
            drift_flag_count = $driftFlagCount
            event_loop_error_seen = $eventLoopErrorSeen
            client_id_in_use_error_seen = $clientIdErrorSeen
            broker_snapshot_pre = $snapshotPre
            broker_snapshot_post = $snapshotPost
            broker_snapshot_connected_ok = ($preSnapshotConnected -and $postSnapshotConnected)
            broker_snapshot_nonzero_ok = $gateSnapshots
            non_qualifying_test_mode = [bool]$NonQualifyingTestMode
            preflight_gate_enabled = [bool](-not $SkipSymbolAvailabilityPreflight)
            preflight_gate_passed = $preflightGatePassed
            preflight_gate_threshold_ratio = $MinSymbolDataAvailabilityRatio
            preflight_data_availability_ratio = $(if ($preflightPayload -ne $null) { [double]$preflightPayload.summary.availability_ratio } else { 1.0 })
            preflight_report_path = $symbolPreflightPath
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
$passedRuns = @($runResults | Where-Object { $_.passed -eq $true }).Count
$sessionPassed = ($allPassed -and $completedRuns -eq $Runs -and $passedRuns -eq $Runs)

$report = [ordered]@{
    step = "1A"
    profile = $Profile
    generated_at_utc = (Get-UtcNow).ToString("o")
    required_window_utc = "08:00-16:00"
    non_qualifying_test_mode = [bool]$NonQualifyingTestMode
    runs_required = $Runs
    runs_completed = $completedRuns
    runs_passed = $passedRuns
    paper_duration_seconds = $effectivePaperDurationSeconds
    min_filled_orders_required = $(if ($NonQualifyingTestMode) { 0 } else { $MinFilledOrders })
    symbol_data_preflight = [ordered]@{
        enabled = [bool](-not $SkipSymbolAvailabilityPreflight)
        min_symbol_data_availability_ratio = $MinSymbolDataAvailabilityRatio
        preflight_min_bars_per_symbol = $PreflightMinBarsPerSymbol
        preflight_period = $PreflightPeriod
        preflight_interval = $PreflightInterval
    }
    session_passed = $sessionPassed
    signoff_ready = $(if ($NonQualifyingTestMode) { $false } else { $sessionPassed })
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
    if (-not $?) {
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
