# PowerShell script to start the FastAPI backend in development mode
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location "$RepoRoot\backend"

if (Test-Path ".\.venv\Scripts\python.exe") {
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
} else {
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
}
