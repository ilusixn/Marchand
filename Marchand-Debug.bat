@echo off
cd /d "%~dp0"
python app.py
echo.
echo Marchand stopped. Log: %USERPROFILE%\.marchand\app.log
pause
