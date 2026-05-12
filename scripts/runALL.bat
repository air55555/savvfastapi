@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%CD%\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: Python not found. Expected one of:
  echo   "%CD%\.venv\Scripts\python.exe"
  echo   "%CD%\venv\Scripts\python.exe"
  exit /b 1
)

echo Using: "%PY%"
echo.

"%PY%" "%CD%\scripts\ingest_hsm_capture.py"
if errorlevel 1 exit /b %errorlevel%

"%PY%" "%CD%\scripts\crop_hsi_cubes.py"
exit /b %errorlevel%
