@echo off
cd /d "%~dp0"
where python >nul 2>nul || (echo Install Python 3.9+ from https://python.org first, with "Add Python to PATH". & pause & goto :eof)
echo Installing the window component (one time)...
python -m pip install --user --quiet pywebview
echo Checking that Marchand loads...
python -c "import sys; sys.path.insert(0,'.'); import server; print('Program loads: OK')" || (echo. & echo Marchand could not load. Copy the error above. & pause & goto :eof)
python -c "import webview; print('Window component: OK')" 2>nul || echo Window component missing: Marchand will use Edge/Chrome in app mode instead.
python make_shortcut.py
echo.
echo Done. Open Marchand from your Desktop or the Start menu.
echo If nothing opens, run Marchand-Debug.bat and also read %USERPROFILE%\.marchand\app.log
pause
