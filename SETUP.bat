# SETUP.bat - Complete local setup for Windows
# Run: SETUP.bat

@echo off
setlocal enabledelayedexpansion

echo.
echo ================================
echo Ayurveda Clinic App - Setup
echo ================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)

echo [OK] Python found

REM Create venv
if not exist "venv" (
    echo [+] Creating virtual environment...
    python -m venv venv
) else (
    echo [OK] Virtual environment exists
)

REM Activate venv
call venv\Scripts\activate.bat
echo [OK] Virtual environment activated

REM Upgrade pip
echo [+] Upgrading pip...
python -m pip install --upgrade pip setuptools wheel >nul 2>&1

REM Install dependencies
echo [+] Installing dependencies (this may take a few minutes)...
pip install -r requirements.txt --no-cache-dir

REM Create .env
if not exist ".env" (
    echo [+] Creating .env file...
    copy .env.example .env
    echo [OK] .env created - edit it with your settings
) else (
    echo [OK] .env already exists
)

REM Create directories
echo [+] Creating directories...
if not exist "templates" mkdir templates
if not exist "static\images" mkdir static\images
if not exist "logs" mkdir logs
if not exist "data" mkdir data

REM Initialize database
echo [+] Initializing database...
alembic upgrade head

REM Verify
echo [+] Verifying environment...
python verify_environment.py

echo.
echo ================================
echo Setup Complete!
echo ================================
echo.
echo To start the app, run:
echo   .\venv\Scripts\activate.bat
echo   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
echo.
echo Then open: http://localhost:8000/new
echo.
pause
