$ErrorActionPreference = "Stop"

Write-Host "Running MindBridge tests..."

python -m unittest discover -s tests -v

$testExitCode = $LASTEXITCODE

if ($testExitCode -ne 0) {
    Write-Host "MindBridge checks failed with exit code $testExitCode." -ForegroundColor Red
    exit $testExitCode
}

Write-Host "All MindBridge checks passed." -ForegroundColor Green