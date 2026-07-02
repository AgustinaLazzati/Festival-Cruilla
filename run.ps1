# Activates the project venv for running demo.py directly.
# demo.py loads ACE-Step 1.5 in-process, so no separate API server is needed.
# Usage: . .\run.ps1     (dot-source so the venv stays active in your shell)

$ErrorActionPreference = "Stop"
$root  = Split-Path -Parent $MyInvocation.MyCommand.Path

# Activate the project venv in the current shell
$activate = Join-Path $root ".venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    Write-Host "Activating .venv"
    & $activate
} else {
    Write-Warning ".venv not found - run install.ps1 first"
}

Write-Host "Venv activated - launch the app now, e.g.:"
Write-Host "  python demo.py"