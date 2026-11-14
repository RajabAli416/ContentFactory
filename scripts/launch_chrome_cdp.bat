@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set PORT=9222
set PROFILE=%cd%\data\chrome-profile
set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
REM Default visual provider UI (Snapgen Muse). For Zsky use:
REM set URL=https://zsky.ai/create
set URL=https://snapgen.ai/app/video-gen/muse?mode=create-new

if not exist "%PROFILE%" mkdir "%PROFILE%"

if not exist %CHROME% (
  echo Chrome not found at %CHROME%
  echo Update CHROME_PATH in .env and this script if needed.
  exit /b 1
)

echo Launching dedicated Chrome with remote debugging on port %PORT%
echo Profile: %PROFILE%
echo Opening: %URL%
echo Log into Snapgen manually in this window if prompted. Do not use your daily profile.
start "ContentFactory Chrome CDP" %CHROME% --remote-debugging-port=%PORT% --user-data-dir="%PROFILE%" --no-first-run --no-default-browser-check "%URL%"

endlocal
