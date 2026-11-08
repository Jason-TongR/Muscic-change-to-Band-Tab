@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0scripts\build_windows.ps1"
if errorlevel 1 (
  echo.
  echo Build failed. Read the error above. Python 3.11 x64 and Inno Setup 6.5+ are required.
  pause
  exit /b 1
)
echo.
echo Complete. Open the release folder for the installer and portable ZIP.
pause
