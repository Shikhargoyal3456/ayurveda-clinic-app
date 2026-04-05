@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "RUNTIME_PYTHON=C:\Users\goyal\AppData\Local\ayurveda-runtime\Scripts\python.exe"

if not exist "%RUNTIME_PYTHON%" (
    echo [ERROR] Working Python runtime not found at "%RUNTIME_PYTHON%".
    echo Recreate or install the runtime before launching the clinic app.
    exit /b 1
)

set "PATH=%~dp0;%PATH%"
for %%I in ("%RUNTIME_PYTHON%") do set "RUNTIME_DIR=%%~dpI"
set "PATH=%RUNTIME_DIR%;%PATH%"
set "PYTHONPATH=%PROJECT_DIR%"

cd /d "%PROJECT_DIR%"
echo Launching Ayurveda Clinic Management System...
"%RUNTIME_PYTHON%" run_server.py
if errorlevel 1 (
    echo [ERROR] Application exited with an error.
    exit /b 1
)
endlocal
