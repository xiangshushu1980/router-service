@echo off
title Router Server Startup

:: Change to the directory where this batch file is located
cd "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found. Please make sure Python is installed and added to system PATH.
    pause
    exit /b 1
)

:: Check if config file exists
if not exist "config.json" (
    echo Warning: config.json not found, using default configuration.
)

:: Start Router server
echo Starting Router server...
python router_server.py

:: Check if startup was successful
if %errorlevel% neq 0 (
    echo Error: Router server failed to start. Please check error messages.
    pause
    exit /b 1
)

pause