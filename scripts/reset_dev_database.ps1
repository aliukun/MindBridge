[CmdletBinding(
    SupportsShouldProcess = $true,
    ConfirmImpact = "High"
)]
param()

$ErrorActionPreference = "Stop"

$projectRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..")
)

$pythonCode = @'
import json

from sqlalchemy.engine import make_url

from app.core.config import PROJECT_ROOT, get_settings


settings = get_settings()
database_url = make_url(settings.database_url)

print(
    json.dumps(
        {
            "project_root": str(PROJECT_ROOT),
            "environment": settings.environment,
            "backend": database_url.get_backend_name(),
            "database": database_url.database,
        },
        ensure_ascii=True,
    )
)
'@

$encodedPythonCode = [System.Convert]::ToBase64String(
    [System.Text.Encoding]::UTF8.GetBytes($pythonCode)
)

Push-Location $projectRoot

try {
    $settingsJson = & python -c (
        "import base64; exec(base64.b64decode(" +
        "'$encodedPythonCode'))"
    )

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to read MindBridge settings."
    }
}
finally {
    Pop-Location
}

$settings = $settingsJson | ConvertFrom-Json

if ($settings.environment.ToLowerInvariant() -ne "development") {
    throw (
        "Database reset is allowed only when " +
        "ENVIRONMENT=development."
    )
}

if ($settings.backend.ToLowerInvariant() -ne "sqlite") {
    throw "Database reset supports SQLite only."
}

if (
    [string]::IsNullOrWhiteSpace($settings.database) -or
    $settings.database -eq ":memory:"
) {
    throw "A file-based SQLite database is required."
}

$configuredProjectRoot = [System.IO.Path]::GetFullPath(
    $settings.project_root
)

$projectRoot = $configuredProjectRoot

if ([System.IO.Path]::IsPathRooted($settings.database)) {
    $databasePath = [System.IO.Path]::GetFullPath(
        $settings.database
    )
}
else {
    $databasePath = [System.IO.Path]::GetFullPath(
        (Join-Path $projectRoot $settings.database)
    )
}

$dataDirectory = [System.IO.Path]::GetFullPath(
    (Join-Path $projectRoot "data")
)

$dataPrefix = $dataDirectory
$separator = [System.IO.Path]::DirectorySeparatorChar.ToString()

if (-not $dataPrefix.EndsWith($separator)) {
    $dataPrefix += $separator
}

if (-not $databasePath.StartsWith(
    $dataPrefix,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw (
        "Refusing to delete a database outside the project " +
        "data directory: $databasePath"
    )
}

if (
    [System.IO.Path]::GetExtension($databasePath) -ine ".db"
) {
    throw "The reset target must have the .db extension."
}

if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) {
    Write-Host "Database file does not exist; nothing to reset:"
    Write-Host $databasePath
    exit 0
}

Write-Host "Stop the MindBridge application before continuing."
Write-Host "Validated development database target:"
Write-Host $databasePath

if ($PSCmdlet.ShouldProcess(
    $databasePath,
    "Delete development SQLite database"
)) {
    Remove-Item -LiteralPath $databasePath
    Write-Host "Development database deleted."
    Write-Host (
        "Start the application to rebuild the empty database " +
        "from ORM metadata."
    )
}
