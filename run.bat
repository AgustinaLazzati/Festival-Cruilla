@echo off
REM Activates the project venv and launches demo.py.
REM demo.py loads ACE-Step 1.5 in-process, so no separate API server is needed.

setlocal
set "ROOT=%~dp0"

if not exist "%ROOT%.venv\Scripts\activate.bat" (
    echo .venv not found - run install.ps1 first
    exit /b 1
)

call "%ROOT%.venv\Scripts\activate.bat"
python "%ROOT%demo.py"