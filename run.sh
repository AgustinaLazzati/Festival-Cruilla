#!/bin/bash
# Activates the project venv and launches demo.py.
# demo.py loads ACE-Step 1.5 in-process, so no separate API server is needed.
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -f "$ROOT/.venv/bin/activate" ]; then
    echo ".venv not found - run install.sh first"
    exit 1
fi

source "$ROOT/.venv/bin/activate"
python "$ROOT/demo.py"
