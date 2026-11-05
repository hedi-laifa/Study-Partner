# PowerShell script to start the React + Vite frontend in development mode
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location "$RepoRoot\frontend"

npm.cmd run dev
