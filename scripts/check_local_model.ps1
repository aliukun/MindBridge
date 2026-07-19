[CmdletBinding()]
param(
    [switch]$VerifyChecksum,
    [switch]$RunInference
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ModelDirectoryName = "mindbridge-qwen2.5-7b-ft"
$ModelFileName = "mindbridge-qwen2.5-7b-ft-q4_k_m.gguf"
$ModelName = if ($env:OLLAMA_MODEL) {
    $env:OLLAMA_MODEL
}
else {
    "mindbridge-qwen2.5-7b-ft:latest"
}
$ExpectedSha256 = "D992DEE2688614EBD24200ED85EF7CA6135DA22C961F8F78C307FD576D8F2C8D"
$OllamaBaseUrl = if ($env:OLLAMA_BASE_URL) {
    $env:OLLAMA_BASE_URL.TrimEnd("/")
}
else {
    "http://127.0.0.1:11434"
}

function Get-CheckedModelPaths {
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

    return [PSCustomObject]@{
        RelativeDirectory = "models/$ModelDirectoryName"
        ModelPath = Join-Path $modelDirectory $ModelFileName
        ModelfilePath = Join-Path $modelDirectory "Modelfile"
    }
}

function Test-HttpBaseUrl {
    param([Parameter(Mandatory = $true)][string]$Value)

    $parsed = $null

    if (-not [Uri]::TryCreate(
        $Value,
        [UriKind]::Absolute,
        [ref]$parsed
    )) {
        return $false
    }

    return (
        $parsed.Scheme -in @("http", "https") -and
        -not [string]::IsNullOrWhiteSpace($parsed.Host) -and
        [string]::IsNullOrEmpty($parsed.UserInfo) -and
        [string]::IsNullOrEmpty($parsed.Query) -and
        [string]::IsNullOrEmpty($parsed.Fragment)
    )
}

function Test-ModelfileSource {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedFile
    )

    $fromLines = @(
        Get-Content -LiteralPath $Path |
            Where-Object { $_ -match "^\s*FROM\s+" }
    )

    if ($fromLines.Count -ne 1) {
        return $false
    }

    $source = ($fromLines[0] -replace "^\s*FROM\s+", "").Trim()

    return $source -eq "./$ExpectedFile"
}

if (-not (Test-HttpBaseUrl -Value $OllamaBaseUrl)) {
    throw "OLLAMA_BASE_URL must be an absolute HTTP(S) URL without credentials, query, or fragment."
}

$paths = Get-CheckedModelPaths
$assetReady = $true

Write-Host "Asset directory: $($paths.RelativeDirectory)"

if (-not (Test-Path -LiteralPath $paths.ModelPath -PathType Leaf)) {
    Write-Host "asset_status=INCOMPLETE (GGUF missing)"
    $assetReady = $false
}

if (-not (Test-Path -LiteralPath $paths.ModelfilePath -PathType Leaf)) {
    Write-Host "asset_status=INCOMPLETE (Modelfile missing)"
    $assetReady = $false
}

if (
    (Test-Path -LiteralPath $paths.ModelfilePath -PathType Leaf) -and
    -not (Test-ModelfileSource `
        -Path $paths.ModelfilePath `
        -ExpectedFile $ModelFileName)
) {
    Write-Host "asset_status=INVALID (FROM does not match GGUF)"
    $assetReady = $false
}

if ($assetReady) {
    Write-Host "asset_status=READY"
}

if (
    $VerifyChecksum -and
    (Test-Path -LiteralPath $paths.ModelPath -PathType Leaf)
) {
    Write-Host "Calculating SHA-256; the 4.68 GB file may take a while..."
    $actualHash = (
        Get-FileHash -LiteralPath $paths.ModelPath -Algorithm SHA256
    ).Hash.ToUpperInvariant()

    if ($actualHash -ne $ExpectedSha256) {
        Write-Host "checksum_status=INVALID"
        $assetReady = $false
    }
    else {
        Write-Host "checksum_status=READY"
    }
}

$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue

if ($null -eq $ollamaCommand) {
    Write-Host "ollama_cli=NOT_FOUND (the script will not install it)"
}
else {
    Write-Host "ollama_cli=FOUND"
}

$serverReady = $false
$registered = $false

try {
    $tags = Invoke-RestMethod `
        -Method Get `
        -Uri "$OllamaBaseUrl/api/tags" `
        -TimeoutSec 10
    $serverReady = $true
    Write-Host "server_status=READY"

    $registeredNames = @(
        $tags.models | ForEach-Object {
            if ($_.name) {
                $_.name
            }
            elseif ($_.model) {
                $_.model
            }
        }
    )

    $registered = $ModelName -in $registeredNames

    if ($registered) {
        Write-Host "registration_status=REGISTERED"
    }
    else {
        Write-Host "registration_status=UNREGISTERED"
    }
}
catch {
    Write-Host "server_status=UNAVAILABLE"
    Write-Host "registration_status=NOT_CHECKED"
}

$inferenceReady = -not $RunInference

if (-not $RunInference) {
    Write-Host "inference_status=NOT_CHECKED"
}
elseif (-not $registered) {
    Write-Host "inference_status=NOT_CHECKED (model is not registered)"
    $inferenceReady = $false
}
else {
    $requestBody = @{
        model = $ModelName
        messages = @(
            @{
                role = "user"
                content = "Reply with one short word: READY"
            }
        )
        stream = $false
        options = @{
            temperature = 0.0
            num_predict = 8
        }
    } | ConvertTo-Json -Depth 6

    try {
        $result = Invoke-RestMethod `
            -Method Post `
            -Uri "$OllamaBaseUrl/api/chat" `
            -ContentType "application/json" `
            -Body $requestBody `
            -TimeoutSec 120

        $inferenceReady = (
            $result.done -eq $true -and
            -not [string]::IsNullOrWhiteSpace($result.message.content)
        )

        if ($inferenceReady) {
            Write-Host "inference_status=READY"
        }
        else {
            Write-Host "inference_status=FAILED"
        }
    }
    catch {
        Write-Host "inference_status=FAILED"
        $inferenceReady = $false
    }
}

if (-not $assetReady -or -not $serverReady -or -not $registered -or -not $inferenceReady) {
    exit 1
}

exit 0
