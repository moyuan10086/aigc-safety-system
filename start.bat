@echo off
chcp 65001 >nul
set ROOT=%~dp0

echo [1/3] Building frontend...
cd /d "%ROOT%frontend"
call npm run build
if %errorlevel% neq 0 (echo [ERROR] Frontend build failed & pause & exit /b)

echo [2/3] Copying .env...
if not exist "%ROOT%backend\.env" copy "%ROOT%backend\.env.example" "%ROOT%backend\.env"

echo [3/3] Starting backend at http://localhost:8010 ...
cd /d "%ROOT%backend"
uv run main.py
pause