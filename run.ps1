<#
.SYNOPSIS
    One-command start for LexiSyncAI on Windows:  .\run.ps1

.DESCRIPTION
    1. Checks for Python 3.11.
    2. Creates .venv if it is missing.
    3. Installs the CPU-only PyTorch wheel (no CUDA download) and the pinned project dependencies.
    4. Checks that Ollama is running and that the configured model is pulled.
       Models are NOT downloaded automatically; the exact command is printed instead.
    5. Starts the application at http://127.0.0.1:8000 and opens the browser.

.PARAMETER SkipInstall
    Skip dependency installation (faster restarts).
.PARAMETER Port
    Port for the web application (default 8000).
.PARAMETER NoBrowser
    Do not open the browser automatically.
#>
param(
    [switch]$SkipInstall,
    [int]$Port = 8000,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Write-Step($message) { Write-Host "==> $message" -ForegroundColor Cyan }
function Fail($message) { Write-Host "ERROR: $message" -ForegroundColor Red; exit 1 }

# 1. Python 3.11 ---------------------------------------------------------------
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Step "Creating virtual environment (.venv) with Python 3.11"
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        & py -3.11 -m venv .venv
    } else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { Fail "Python 3.11 was not found. Install it from https://www.python.org/downloads/ and retry." }
        & python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $venvPython)) {
        Fail "Could not create the virtual environment. Is Python 3.11 installed (py -3.11 --version)?"
    }
}

$version = & $venvPython -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ($version -ne "3.11") { Fail "The virtual environment uses Python $version; LexiSyncAI requires Python 3.11. Delete .venv and retry." }
Write-Step "Python $version (.venv)"

# 2. Dependencies --------------------------------------------------------------
if (-not $SkipInstall) {
    $hasTorch = & $venvPython -c "import importlib.util; print(importlib.util.find_spec('torch') is not None)"
    if ($hasTorch -ne "True") {
        Write-Step "Installing CPU-only PyTorch (no CUDA download)"
        & $venvPython -m pip install --quiet torch --index-url https://download.pytorch.org/whl/cpu
        if ($LASTEXITCODE -ne 0) { Fail "PyTorch installation failed. Check your internet connection." }
    }
    Write-Step "Installing pinned project dependencies (first run can take several minutes)"
    & $venvPython -m pip install --quiet -e ".[dev]"
    if ($LASTEXITCODE -ne 0) { Fail "Dependency installation failed. See the pip output above." }
}

# 3. Configuration --------------------------------------------------------------
if (-not (Test-Path -LiteralPath ".env") -and (Test-Path -LiteralPath ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Step "Created .env from .env.example"
}
$model = "qwen2.5:3b"
$ollamaUrl = "http://localhost:11434"
if (Test-Path -LiteralPath ".env") {
    foreach ($line in Get-Content ".env") {
        if ($line -match "^\s*OLLAMA_MODEL\s*=\s*(.+)\s*$") { $model = $Matches[1].Trim() }
        if ($line -match "^\s*OLLAMA_BASE_URL\s*=\s*(.+)\s*$") { $ollamaUrl = $Matches[1].Trim() }
    }
}

# 4. Ollama ----------------------------------------------------------------------
Write-Step "Checking Ollama at $ollamaUrl"
try {
    $tags = Invoke-RestMethod -Uri "$ollamaUrl/api/tags" -TimeoutSec 5
    $names = @($tags.models | ForEach-Object { $_.name })
    if ($names -contains $model) {
        Write-Host "    Ollama is running and '$model' is available." -ForegroundColor Green
    } else {
        Write-Host "    Ollama is running, but the model '$model' is not pulled." -ForegroundColor Yellow
        Write-Host "    Download it (about 2 GB) with:   ollama pull $model" -ForegroundColor Yellow
        Write-Host "    The app will start; questions will fail until the model is available." -ForegroundColor Yellow
    }
} catch {
    Write-Host "    Ollama is not reachable at $ollamaUrl." -ForegroundColor Yellow
    Write-Host "    Install it from https://ollama.com/download, start the Ollama app, then run:  ollama pull $model" -ForegroundColor Yellow
    Write-Host "    The app will start; indexing works, but answering needs Ollama." -ForegroundColor Yellow
}

# 5. Launch -----------------------------------------------------------------------
Write-Step "Starting LexiSyncAI on http://127.0.0.1:$Port  (Ctrl+C to stop)"
$arguments = @("app.py", "--port", "$Port")
if ($NoBrowser) { $arguments += "--no-browser" }
& $venvPython @arguments
exit $LASTEXITCODE
