@echo off
setlocal

cd /d "%~dp0\.."

set "PY=%CD%\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: venv python not found at "%PY%"
  pause
  exit /b 1
)

set "ROOT=D:\HSM_CAPTURE"
set "TOL=5"

"%PY%" scripts\ingest_hsm_capture.py --root "%ROOT%" --tolerance-seconds %TOL%

echo.
echo Done.
pause

