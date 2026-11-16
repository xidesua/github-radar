@echo off
rem Launch the GitHub Radar desktop window (no console window left behind).
rem Prefers pythonw.exe so nothing black flashes; falls back to python.exe.
setlocal
cd /d "%~dp0"

where pythonw >nul 2>nul
if not errorlevel 1 (
  start "" pythonw "%~dp0open_app.py"
  goto :eof
)

where python >nul 2>nul
if not errorlevel 1 (
  start "" python "%~dp0open_app.py"
  goto :eof
)

echo Python not found.
echo Install Python 3.10+ and run: pip install pywebview
pause
