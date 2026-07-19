[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [ValidateNotNullOrEmpty()]
    [string]$ModelName = "mindbridge-qwen2.5-7b-ft:latest",
    [switch]$VerifyChecksum
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ModelDirectoryName = "mindbridge-qwen2.5-7b-ft"
$ModelFileName = "mindbridge-qwen2.5-7b-ft-q4_k_m.gguf"
$ExpectedSha256 = "D992DEE2688614EBD24200ED85EF7CA6135DA22C961F8F78C307FD576D8F2C8D"

$projectRoot = [IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..")
)
$modelsRoot = [IO.Path]::GetFullPath(
    (Join-Path $projectRoot "models")
)
$modelDirectory = [IO.Path]::GetFullPath(
    (Join-Path $modelsRoot $ModelDirectoryName)
)
$modelsPrefix = $modelsRoot.TrimEnd(
    [IO.Path]::DirectorySeparatorChar,
    [IO.Path]::AltDirectorySeparatorChar
) + [IO.Path]::DirectorySeparatorChar

if (-not $modelDirectory.StartsWith(
    $modelsPrefix,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Model directory escaped the project models directory."
}

$modelPath = Join-Path $modelDirectory $ModelFileName
$modelfilePath = Join-Path $modelDirectory "Modelfile"

if (-not (Test-Path -LiteralPath $modelPath -PathType Leaf)) {
    throw "The expected GGUF file is missing. This script will not download or copy it."
}

if (-not (Test-Path -LiteralPath $modelfilePath -PathType Leaf)) {
    throw "The expected Modelfile is missing."
}

$fromLines = @(
    Get-Content -LiteralPath $modelfilePath |
        Where-Object { $_ -match "^\s*FROM\s+" }
)

if ($fromLines.Count -ne 1) {
    throw "Modelfile must contain exactly one FROM directive."
}

$source = ($fromLines[0] -replace "^\s*FROM\s+", "").Trim()

if ($source -ne "./$ModelFileName") {
    throw "Modelfile FROM does not match the expected GGUF filename."
}

if ($VerifyChecksum) {
    Write-Host "Calculating SHA-256; the 4.68 GB file may take a while..."
    $actualHash = (
        Get-FileHash -LiteralPath $modelPath -Algorithm SHA256
    ).Hash.ToUpperInvariant()

    if ($actualHash -ne $ExpectedSha256) {
        throw "GGUF SHA-256 does not match the documented model asset."
    }

    Write-Host "checksum_status=READY"
}

$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue

if ($null -eq $ollamaCommand) {
    throw "Ollama CLI was not found. This script will not install it."
}

$ollamaExecutable = $ollamaCommand.Source

if ([string]::IsNullOrWhiteSpace($ollamaExecutable)) {
    $ollamaExecutable = $ollamaCommand.Path
}

if ($PSCmdlet.ShouldProcess(
    $ModelName,
    "Register the local GGUF with Ollama using the checked Modelfile"
)) {
    & $ollamaExecutable create $ModelName -f $modelfilePath

    if ($LASTEXITCODE -ne 0) {
        throw (
            "ollama create failed with exit code $LASTEXITCODE. " +
            "On Windows, if the user profile contains non-ASCII characters, " +
            "set OLLAMA_MODELS to an ASCII-only absolute directory and fully " +
            "restart Ollama before retrying."
        )
    }

    Write-Host "registration_status=REGISTERED model=$ModelName"
}
