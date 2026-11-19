@echo off
setlocal
cd /d "%~dp0"

title Abaqus Agent
echo ==============================================
echo   Abaqus Agent - one-click start (port 8502)
echo ==============================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating virtual environment ...
  python -m venv .venv
  if errorlevel 1 goto fail
  echo [2/3] Installing dependencies (needs network, may take a few minutes) ...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto fail
) else (
  echo [1/3] Existing virtual environment found, skip install.
)

if not exist ".env" (
  if exist ".env.example" copy ".env.example" ".env" >nul
  echo.
  echo [i] Created .env from .env.example.
  echo     Open .env and fill LLM_API_KEY, then run start.bat again.
  echo     The 3D preview and model generation still work without a key.
  pause
  exit /b 0
)

echo [3/3] Starting web UI: http://localhost:8502
start "" "http://localhost:8502"
".venv\Scripts\python.exe" -m agent.web
goto end

:fail
echo.
echo [ERROR] Setup failed. Make sure Python 3.10+ is on PATH and network works.
pause

:end
pause
