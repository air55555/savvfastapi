REM @echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%CD%\venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: Python not found. Expected one of:
  echo   "%CD%\.venv\Scripts\python.exe"
  echo   "%CD%\venv\Scripts\python.exe"
  REM exit /b 1
)

echo Using: "%PY%"
echo.

C:\Users\LRS\PycharmProjects\savvfastapi\.venv\Scripts\python.exe C:\Users\LRS\PycharmProjects\savvfastapi\scripts\ingest_hsm_capture.py
C:\Users\LRS\PycharmProjects\savvfastapi\.venv\Scripts\python.exe  C:\Users\LRS\PycharmProjects\savvfastapi\scripts\crop_hsi_cubes.py
C:\Users\LRS\PycharmProjects\savvfastapi\.venv\Scripts\python.exe  C:\Users\LRS\PycharmProjects\savvfastapi\scripts\process_all_hsm_capture.py -k 2
C:\Users\LRS\PycharmProjects\savvfastapi\.venv\Scripts\python.exe  C:\Users\LRS\PycharmProjects\savvfastapi\scripts\collect_detect_files.py --wildcard cr10p_cheese_?_2cluster0p --out d:/HSM_detect_2clust
copy C:\Users\LRS\PycharmProjects\savvfastapi\etc\cube_27_03_18_11_16_cr10p_cheese_1_2cluster0p.png  D:\HSM_detect_2clust
C:\Users\LRS\PycharmProjects\savvfastapi\.venv\Scripts\python.exe  C:\Users\LRS\PycharmProjects\savvfastapi\scripts\find_similar_middle_particles.py --scan-dir D:\HSM_detect_2clust
C:\Users\LRS\PycharmProjects\savvfastapi\.venv\Scripts\python.exe  C:\Users\LRS\PycharmProjects\savvfastapi\scripts\analyze_palletes_scan_background.py --scan-dir D:\HSM_detect_2clust\filtered
C:\Users\LRS\PycharmProjects\savvfastapi\.venv\Scripts\python.exe  C:\Users\LRS\PycharmProjects\savvfastapi\scripts\copy_capture_dirs_to_filtered.py
C:\Users\LRS\PycharmProjects\savvfastapi\.venv\Scripts\python.exe  C:\Users\LRS\PycharmProjects\savvfastapi\scripts\batch_regions2_averages.py --root D:\HSM_detect_2clust\filtered --db C:\Users\LRS\PycharmProjects\savvfastapi\etc\minerals_ecostress.db
C:\Users\LRS\PycharmProjects\savvfastapi\.venv\Scripts\python.exe  C:\Users\LRS\PycharmProjects\savvfastapi\scripts
C:\Users\LRS\PycharmProjects\savvfastapi\.venv\Scripts\python.exe  C:\Users\LRS\PycharmProjects\savvfastapi\scripts
"%PY%" "%CD%\scripts\crop_hsi_cubes.py"
exit /b %errorlevel%
