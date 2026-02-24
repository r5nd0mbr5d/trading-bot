# Runs one Step 1A session sequentially. Stops on first failure.
$ErrorActionPreference = "Stop"

Write-Host "[1/5] Health check"
python main.py uk_health_check --profile uk_paper --strict-health

Write-Host "[2/5] Paper trial (30 min)"
python main.py paper_trial --confirm-paper-trial --profile uk_paper --paper-duration-seconds 1800 --skip-rotate

Write-Host "[3/5] Paper session summary export"
python main.py paper_session_summary --profile uk_paper --output-dir reports/uk_tax

Write-Host "[4/5] UK tax export"
python main.py uk_tax_export --profile uk_paper --output-dir reports/uk_tax

Write-Host "[5/5] Strict reconcile"
python main.py paper_reconcile --profile uk_paper --output-dir reports/uk_tax --expected-json reports/uk_tax/paper_session_summary.json --strict-reconcile

Write-Host "Session complete. Review reports/uk_tax for artifacts."
