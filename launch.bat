@echo off
setlocal
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.9 or newer is required.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto fail
.venv\Scripts\python.exe -m api_providers %*
if errorlevel 1 goto fail
exit /b 0
:fail
 echo API Providers could not start. See the error above.
 pause
 exit /b 1
