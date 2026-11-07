@echo off
cd /d "%~dp0\.."
if exist ".venv-desktop\Scripts\pythonw.exe" (
  start "" ".venv-desktop\Scripts\pythonw.exe" "desktop.py"
) else (
  echo Please run: py -3.11 scripts\setup_desktop.py
  pause
)
