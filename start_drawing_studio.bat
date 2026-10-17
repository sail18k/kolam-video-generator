@echo off
chcp 65001 >nul
title Kolam Interactive Drawing Studio V2

echo ========================================================================
echo   🎨  HEADLESS KOLAM VIDEO GENERATOR V2 - INTERACTIVE DRAWING STUDIO
echo ========================================================================
echo.

cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH!
    echo Please install Python 3.10 and ensure "Add Python to PATH" is checked.
    pause
    exit /b 1
)

:: Discover LAN IPv4 address
for /f "tokens=*" %%i in ('python -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(s.getsockname()[0]); s.close()" 2^>nul') do set LAN_IP=%%i

if "%LAN_IP%"=="" (
    set LAN_IP=127.0.0.1
)

echo [NETWORK DISCOVERY]
echo   💻 Host Access:        http://localhost:8000
echo                          http://127.0.0.1:8000
echo   📱 LAN / Wi-Fi Access: http://%LAN_IP%:8000
echo   ⚡ Drawing Speed:      1.2x (smooth natural hand)
echo.
echo ========================================================================
echo   💡 HOW TO USE ON PHONE OR TABLET:
echo      1. Connect your phone or tablet to the SAME Wi-Fi network as this PC.
echo      2. Open your mobile browser and enter: http://%LAN_IP%:8000
echo      3. Upload a reference sketch, adjust opacity, and draw with touch/stylus!
echo.
echo   🛡️ WINDOWS DEFENDER FIREWALL NOTE:
echo      If your mobile device cannot connect, run PowerShell as Administrator:
echo      New-NetFirewallRule -DisplayName "Kolam Studio Port 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow -Profile Private
echo ========================================================================
echo.

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:: Automatically open default browser on host PC after 2 seconds in background
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

:: Launch web application server
python web_app.py --host 0.0.0.0 --port 8000 --drawing-speed 1.2

pause
