@echo off
setlocal

cd /d "%~dp0\.."
set "PY=%CD%\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: venv python not found at "%PY%"
  pause
  exit /b 1
)

REM Creates local HSM_CAPTURE with cube_* test folders and matching DB times.
"%PY%" scripts\create_hsm_capture_testdata.py --root "HSM_CAPTURE" --count 3

echo.
echo Done.
pause

