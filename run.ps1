# Starts the ACE-Step API in the background, leaving this terminal free.
# The job is tied to this PowerShell session: closing the terminal stops it.
# Usage: . .\run.ps1     (dot-source so the venv stays active in your shell)

$ErrorActionPreference = "Stop"
$root  = Split-Path -Parent $MyInvocation.MyCommand.Path
$aceDir = Join-Path $root "models\ACE-Step-1.5"

# Activate the project venv in the current shell
$activate = Join-Path $root ".venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    Write-Host "Activating .venv"
    & $activate
} else {
    Write-Warning ".venv not found - run install.ps1 first"
}

# Make sure uv is on PATH
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# Launch acestep-api as a background job (runs from the ACE-Step project dir)
Write-Host "Starting acestep-api in background..."
$job = Start-Job -Name "acestep-api" -ScriptBlock {
    param($dir)
    Set-Location $dir
    & uv run acestep-api
} -ArgumentList $aceDir

Write-Host "acestep-api job started (Id $($job.Id))."
Write-Host "  Logs : Receive-Job -Name acestep-api -Keep"
Write-Host "  Stop : Stop-Job -Name acestep-api; Remove-Job -Name acestep-api"
Write-Host "Terminal is free - launch your python script now, e.g.:"
Write-Host "  python main.py --image inputs/user.png --language ca --with-music"
