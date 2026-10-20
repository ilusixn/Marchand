@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw "%~dp0app.py" & goto :eof)
where pyw >nul 2>nul && (start "" pyw -3 "%~dp0app.py" & goto :eof)
where python >nul 2>nul && (start "" python "%~dp0app.py" & goto :eof)
echo Python 3.9 or newer is required. Install it from https://python.org and tick "Add Python to PATH".
pause
