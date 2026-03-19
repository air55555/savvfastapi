@echo off
setlocal

REM Run from repo root even if double-clicked
cd /d "%~dp0\.."

REM Use project venv python
set "PY=%CD%\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: venv python not found at "%PY%"
  echo Create venv first: py -m venv venv
  echo Then install requirements: venv\Scripts\pip.exe install -r requirements.txt
  pause
  exit /b 1
)

REM Insert 10 random test records (plus 3 canonical ones)
"%PY%" scripts\seed_palletes_scan_testdata.py --n 10

echo.
echo Done.
pause

