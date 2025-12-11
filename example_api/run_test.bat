@echo off
REM Data Catalog API - Test Mode Runner
REM This script runs the API in test mode using local _data files

echo 🧪 Starting Data Catalog API in TEST MODE
echo ==========================================
echo Mode: TEST MODE (using local _data files)
echo Port: 8000
echo.

REM Set environment variables for test mode
set TEST_MODE=true
set PASSTHROUGH_MODE=false
set PORT=8000

echo Environment variables set:
echo   TEST_MODE=%TEST_MODE%
echo   PASSTHROUGH_MODE=%PASSTHROUGH_MODE%
echo   PORT=%PORT%
echo.

echo Starting API...
echo Press Ctrl+C to stop
echo.

REM Run the API
python main.py

pause
