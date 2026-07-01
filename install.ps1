# Creates a Python venv and installs requirements.txt
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1 [-Cuda cu124]
param(
    [string]$Cuda = "cu124"   # e.g. cu118, cu121, cu124, or cpu
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venv = Join-Path $root ".venv"

# Pick a Python launcher
$py = (Get-Command py -ErrorAction SilentlyContinue)
if ($py) { $python = "py"; $pythonArgs = @("-3.10") } else { $python = "python"; $pythonArgs = @() }

if (-not (Test-Path $venv)) {
    Write-Host "Creating venv at $venv"
    & $python @pythonArgs -m venv $venv
} else {
    Write-Host "venv already exists at $venv"
}

$vpython = Join-Path $venv "Scripts\python.exe"

Write-Host "Upgrading pip"
& $vpython -m pip install --upgrade pip

Write-Host "Installing torch ($Cuda)"
& $vpython -m pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url "https://download.pytorch.org/whl/$Cuda"

Write-Host "Installing requirements"
& $vpython -m pip install -r (Join-Path $root "requirements.txt")

# ── ACE-Step 1.5 (cloned into models/, installed with uv) ──────────────────
$modelsDir = Join-Path $root "models"
$aceDir    = Join-Path $modelsDir "ACE-Step-1.5"

if (-not (Test-Path $aceDir)) {
    Write-Host "Cloning ACE-Step-1.5 into $modelsDir"
    New-Item -ItemType Directory -Force -Path $modelsDir | Out-Null
    & git clone https://github.com/ace-step/ACE-Step-1.5.git $aceDir
} else {
    Write-Host "ACE-Step-1.5 already exists at $aceDir"
}

# Install uv if missing
$uv = (Get-Command uv -ErrorAction SilentlyContinue)
if (-not $uv) {
    Write-Host "Installing uv"
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    # uv lands in ~\.local\bin; add to PATH for this session
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

Write-Host "Running uv sync in ACE-Step-1.5"
Push-Location $aceDir
& uv sync
Pop-Location

Write-Host "Done. Activate with: .\.venv\Scripts\Activate.ps1"
