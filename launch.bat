@echo off
title API Provider Manager
color 0A

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install requests pyperclip --quiet

if errorlevel 1 (
    color 0C
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Launching API Provider Manager...
echo.
python main.py

if errorlevel 1 (
    color 0C
    echo.
    echo ERROR: Application failed to start
    pause
    exit /b 1
)
