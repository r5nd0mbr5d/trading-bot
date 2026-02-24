param(
    [string]$ReportPath = "reports/uk_tax/step1a_burnin/step1a_burnin_latest.json",
    [string]$BacklogPath = "IMPLEMENTATION_BACKLOG.md"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ReportPath)) {
    throw "Report not found: $ReportPath"
}

if (-not (Test-Path $BacklogPath)) {
    throw "Backlog not found: $BacklogPath"
}

$report = Get-Content -Path $ReportPath -Raw | ConvertFrom-Json
if (-not $report) {
    throw "Unable to parse report JSON: $ReportPath"
}

$generatedUtc = $report.generated_at_utc
$sessionPassed = [bool]$report.session_passed
$runsRequired = [int]$report.runs_required
$runsCompleted = [int]$report.runs_completed
$runsPassed = [int]$report.runs_passed
$outputDir = [string]$report.output_dir

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("")
$lines.Add("### Step 1A Auto Evidence Log")
$lines.Add("")
$lines.Add("- Generated (UTC): $generatedUtc")
$lines.Add("- Source report: $ReportPath")
$lines.Add("- Session output dir: $outputDir")
$lines.Add("- Session pass: $sessionPassed")
$lines.Add("- Runs: $runsPassed / $runsRequired passed ($runsCompleted completed)")
$lines.Add("")

$runResults = @($report.run_results)
foreach ($run in $runResults) {
    $runId = [int]$run.run
    $passed = [bool]$run.passed
    $utcStart = [string]$run.utc_start
    $inWindow = [bool]$run.in_window
    $reason = [string]$run.reason

    $lines.Add("#### Auto Run $runId")
    $lines.Add("- Date (UTC): $utcStart")
    $lines.Add("- Window check: $inWindow")
    $lines.Add("- Result: $passed")

    if ($run.PSObject.Properties.Name -contains "filled_order_count") {
        $lines.Add("- filled_order_count: $($run.filled_order_count)")
    }
    if ($run.PSObject.Properties.Name -contains "min_filled_orders_required") {
        $lines.Add("- min_filled_orders_required: $($run.min_filled_orders_required)")
    }
    if ($run.PSObject.Properties.Name -contains "drift_flag_count") {
        $lines.Add("- drift_flag_count: $($run.drift_flag_count)")
    }
    if ($run.PSObject.Properties.Name -contains "event_loop_error_seen") {
        $lines.Add("- event_loop_error_seen: $($run.event_loop_error_seen)")
    }
    if ($run.PSObject.Properties.Name -contains "client_id_in_use_error_seen") {
        $lines.Add("- client_id_in_use_error_seen: $($run.client_id_in_use_error_seen)")
    }
    if ($run.PSObject.Properties.Name -contains "broker_snapshot_nonzero_ok") {
        $lines.Add("- broker_snapshot_nonzero_ok: $($run.broker_snapshot_nonzero_ok)")
    }

    if ($run.PSObject.Properties.Name -contains "artifacts") {
        $artifacts = $run.artifacts
        $lines.Add("- Artifacts:")
        foreach ($prop in $artifacts.PSObject.Properties) {
            $lines.Add("  - $($prop.Name): $($prop.Value)")
        }
    }

    if ($run.PSObject.Properties.Name -contains "logs") {
        $logs = $run.logs
        $lines.Add("- Logs:")
        foreach ($prop in $logs.PSObject.Properties) {
            $lines.Add("  - $($prop.Name): $($prop.Value)")
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($reason)) {
        $lines.Add("- Notes: $reason")
    }
    if ($run.PSObject.Properties.Name -contains "error" -and -not [string]::IsNullOrWhiteSpace([string]$run.error)) {
        $lines.Add("- Error: $($run.error)")
    }

    $lines.Add("")
}

$lines.Add("---")
$lines.Add("")

$existing = Get-Content -Path $BacklogPath -Raw
$payload = ($lines -join "`r`n")

if ($existing -match "### Step 1A Auto Evidence Log") {
    $existing = $existing -replace "### Step 1A Auto Evidence Log[\s\S]*?\r?\n---\r?\n", ""
}

Set-Content -Path $BacklogPath -Value ($existing.TrimEnd() + "`r`n`r`n" + $payload) -Encoding UTF8
Write-Host "Appended Step 1A evidence to $BacklogPath from $ReportPath"
