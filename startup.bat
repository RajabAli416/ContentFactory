@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment missing. Run setup.bat first.
  exit /b 1
)

if not exist ".env" copy /Y ".env.example" ".env" >nul

call .venv\Scripts\activate.bat

REM Note: do NOT use --reload on Windows for production runs.
REM Reload can force a SelectorEventLoop that breaks Playwright/FFmpeg subprocesses.
echo Starting ContentFactory backend on http://127.0.0.1:8000 ...
start "ContentFactory Backend" cmd /k "cd /d ""%~dp0"" && call .venv\Scripts\activate.bat && set PYTHONPATH=backend && uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --loop asyncio"

timeout /t 2 /nobreak >nul

echo Starting ContentFactory frontend on http://127.0.0.1:5173 ...
start "ContentFactory Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:5173"

echo.
echo Backend:  http://127.0.0.1:8000/docs
echo Frontend: http://127.0.0.1:5173
echo Close the Backend/Frontend console windows to stop.
echo Tip: restart the backend window after code changes (reload is disabled on purpose).
endlocal
