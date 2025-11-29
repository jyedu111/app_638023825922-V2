@echo off
title Student Monitor Installation
echo.
echo ====================================================
echo Student Monitor System - Client Installation
echo ====================================================
echo.

:: Change to student client directory
cd /d "%~dp0for stu"
if %ERRORLEVEL% neq 0 (
    echo Failed to find student client directory!
    pause
    exit /b 1
)

:: Check Python installation
set "PYTHON=python"
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    set "PYTHON=py"
    where py >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo Python not found! Please install Python 3.9+ first
        pause
        exit /b 1
    )
)

echo Installing required dependencies...
echo.

:: Install dependencies
%PYTHON% -m pip install --upgrade pip
%PYTHON% -m pip install requests Pillow psutil pywin32

if %ERRORLEVEL% neq 0 (
    echo.
    echo Failed to install dependencies! Check network connection and try again
    pause
    exit /b 1
)

echo.
echo Dependencies installed successfully!
echo.
echo Starting monitoring agent...
echo Note: This window needs to remain open, you can minimize it

echo.
%PYTHON% student_agent.py

pause
