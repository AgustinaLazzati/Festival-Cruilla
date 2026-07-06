#!/bin/bash
# Creates a Python venv and installs torch + requirements.txt
# Usage: ./install.sh
# Override defaults with env vars, e.g.: PYTHON=python3.11 CUDA=cu124 ./install.sh
set -e

PYTHON="${PYTHON:-python}"
CUDA="${CUDA:-cu128}"   # e.g. cu118, cu121, cu124, cu128, cu130, or cpu
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv"

if [ ! -d "$VENV" ]; then
    echo "Creating venv at $VENV"
    "$PYTHON" -m venv "$VENV"
else
    echo "venv already exists at $VENV"
fi

echo "Upgrading pip"
"$VENV/bin/python" -m pip install --upgrade pip

echo "Installing torch ($CUDA)"
"$VENV/bin/python" -m pip install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url "https://download.pytorch.org/whl/$CUDA"

echo "Installing requirements"
"$VENV/bin/python" -m pip install -r "$ROOT/requirements.txt"

echo "Done. Activate with: source .venv/bin/activate"
