@echo off
cd /d "%~dp0"
echo ===================================================
echo     Reset YouTube Account / Channel Selection
echo ===================================================
echo.
python upload_to_youtube.py --reset-auth
echo.
pause
