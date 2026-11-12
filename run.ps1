$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    py -3.11 -m venv (Join-Path $PSScriptRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python 3.11 virtual environment." }
}

& $python -m pip install -e .
if ($LASTEXITCODE -ne 0) { throw "Project dependency installation failed." }

if (-not (Get-Process -Name "ollama" -ErrorAction SilentlyContinue)) {
    Write-Warning "Ollama does not appear to be running. Start Ollama and retry if answer generation cannot connect."
}

& $python -m streamlit run app.py
exit $LASTEXITCODE
