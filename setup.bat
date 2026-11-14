@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo  ContentFactory Setup
echo ============================================

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found on PATH. Install Python 3.11+.
  exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js not found on PATH. Install Node 18+.
  exit /b 1
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo [WARN] ffmpeg not found on PATH. Install FFmpeg and retry.
) else (
  echo [OK] ffmpeg found
)

where ffprobe >nul 2>&1
if errorlevel 1 (
  echo [WARN] ffprobe not found on PATH.
) else (
  echo [OK] ffprobe found
)

if not exist ".venv" (
  echo Creating Python virtual environment...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
if errorlevel 1 (
  echo [ERROR] Backend dependency install failed.
  exit /b 1
)

echo Installing Playwright Chromium (optional for live Snapgen/Zsky)...
playwright install chromium >nul 2>&1

echo Installing frontend dependencies...
pushd frontend
call npm install
if errorlevel 1 (
  echo [ERROR] Frontend dependency install failed.
  popd
  exit /b 1
)
popd

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo Created .env from .env.example — set GEMINI_API_KEY before running.
)

for %%D in (data\projects data\assets data\exports data\logs data\database data\chrome-profile) do (
  if not exist "%%D" mkdir "%%D"
)

echo.
echo Setup complete.
echo Next: run startup.bat
echo For visuals: run scripts\launch_chrome_cdp.bat then log into Snapgen/Zsky
echo Default visual provider is Snapgen (VIDEO_GEN_PROVIDER=snapgen). Use zsky to switch.
endlocal
