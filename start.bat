@echo off
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo [Error] Python virtual environment not found.
    echo         Please double-click setup.bat first to install.
    pause
    exit /b 1
)

if not exist backend\.env (
    echo [Error] backend\.env not found.
    echo.
    echo         Copy backend\.env.example to backend\.env and fill in:
    echo           DASHSCOPE_API_KEY  - your Bailian API key
    echo           JWT_SECRET         - a random string, generate with:
    echo                                python -c "import secrets; print(secrets.token_urlsafe(48))"
    echo.
    echo         The backend refuses to start without JWT_SECRET.
    pause
    exit /b 1
)

findstr /B /C:"JWT_SECRET=" backend\.env >nul
if errorlevel 1 (
    echo [Error] JWT_SECRET is missing from backend\.env.
    echo         Generate one with:
    echo           python -c "import secrets; print(secrets.token_urlsafe(48))"
    pause
    exit /b 1
)

echo [1/2] Starting backend server  (port 8000) ...
start "RAG-Backend" /D "%~dp0backend" cmd /k "..\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [2/2] Starting frontend server (port 5173) ...
start "RAG-Frontend" /D "%~dp0frontend" cmd /k "npm run dev"

echo Waiting 4 seconds for services to start, then opening browser ...
timeout /t 4 /nobreak >nul
start "" http://localhost:5173

echo.
echo ==================================================
echo   Startup done.
echo     Backend   : http://127.0.0.1:8000
echo     Frontend  : http://localhost:5173
echo   Keep the two service windows open.
echo   Close them to stop the system.
echo ==================================================
echo.
echo You can close THIS window now (services keep running).
pause >nul