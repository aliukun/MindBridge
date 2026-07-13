$ErrorActionPreference = "Stop"

Write-Host "Running MindBridge tests..."

python -m unittest discover -s tests -v

Write-Host "All MindBridge checks passed."