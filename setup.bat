@echo off
cd /d "%~dp0"

echo ============================================
echo   E-commerce Knowledge QA System - Setup
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [Error] Python not found.
    echo         Install Python 3.10+ and check "Add to PATH".
    pause
    exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
    echo [Error] Node.js not found. Install Node.js first.
    pause
    exit /b 1
)

if not exist venv (
    echo [1/4] Creating Python virtual environment ...
    python -m venv venv
)

echo [2/4] Installing backend dependencies (a bit slow, please wait) ...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r backend\requirements.txt
if errorlevel 1 (
    call deactivate
    echo [Error] Backend dependency install failed. Check network and retry.
    pause
    exit /b 1
)
call deactivate

echo [3/4] Installing frontend dependencies ...
cd /d "%~dp0frontend"
call npm install
if errorlevel 1 (
    echo [Error] Frontend dependency install failed. Check network and retry.
    pause
    exit /b 1
)
cd /d "%~dp0"

echo.
echo [4/4] All dependencies installed successfully!
echo.
echo Notices:
echo   1. Make sure DASHSCOPE_API_KEY is filled in backend\.env
echo   2. First upload/question downloads the bge-m3 model (about 2GB).
echo   3. Then double-click start.bat to launch the system.
echo.
pause