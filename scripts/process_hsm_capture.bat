@echo off
setlocal
cd /d "%~dp0\.."
set "PY=%CD%\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: venv python not found. Use venv or .venv\Scripts\python.exe
  pause
  exit /b 1
)
"%PY%" scripts\process_hsm_capture.py %*
echo.
pause
