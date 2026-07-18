$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-PythonStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Host "`n==> $Name" -ForegroundColor Cyan
    & python @Arguments
    $exitCode = $LASTEXITCODE

    if ($exitCode -ne 0) {
        throw "$Name failed with exit code $exitCode."
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot

try {
    Invoke-PythonStep -Name "Dependency consistency" -Arguments @(
        "-m", "pip", "check"
    )

    Invoke-PythonStep -Name "Ruff lint" -Arguments @(
        "-m", "ruff", "check", "app", "tests"
    )

    Invoke-PythonStep -Name "Ruff format check" -Arguments @(
        "-m", "ruff", "format", "--check", "app", "tests"
    )

    Invoke-PythonStep -Name "mypy" -Arguments @(
        "-m", "mypy", "app"
    )

    Invoke-PythonStep -Name "Python byte-code compilation" -Arguments @(
        "-m", "compileall", "-q", "app", "tests"
    )

    New-Item -ItemType Directory -Force -Path "target" | Out-Null

    Invoke-PythonStep -Name "Clear old coverage data" -Arguments @(
        "-m", "coverage", "erase"
    )

    Invoke-PythonStep -Name "Unit tests with coverage" -Arguments @(
        "-m", "coverage", "run", "-m", "unittest", "discover",
        "-s", "tests", "-v"
    )

    Invoke-PythonStep -Name "Coverage threshold" -Arguments @(
        "-m", "coverage", "report"
    )

    Write-Host "`nAll MindBridge checks passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
