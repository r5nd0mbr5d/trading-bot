param(
    [string]$Message = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Message)) {
    $Message = "wip: keep changes $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
}

$changes = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Unable to read git status"
}
if ([string]::IsNullOrWhiteSpace(($changes -join ""))) {
    Write-Host "No changes to commit."
    exit 0
}

git add -A
if ($LASTEXITCODE -ne 0) {
    throw "git add failed"
}

git commit -m "$Message"
if ($LASTEXITCODE -ne 0) {
    throw "git commit failed"
}

$branch = (git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) {
    throw "Unable to determine current branch"
}

git push origin $branch
if ($LASTEXITCODE -ne 0) {
    throw "git push failed"
}

Write-Host "Committed and pushed to origin/$branch"
