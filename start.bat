@echo off
title Kolam Interactive Drawing Studio - Starter

echo ========================================================================
echo   [START] KOLAM VIDEO GENERATOR V2 - INTERACTIVE DRAWING STUDIO
echo ========================================================================
echo.

pushd "%~dp0."

:: Default configuration
set PORT=8000
set NO_BROWSER=0
set FOREGROUND=0

:: Parse CLI arguments (e.g. start.bat 8080 --no-browser --foreground)
:parse_args
if "%~1"=="" goto done_args
if /i "%~1"=="--no-browser" set NO_BROWSER=1
if /i "%~1"=="/nobrowser" set NO_BROWSER=1
if /i "%~1"=="-n" set NO_BROWSER=1
if /i "%~1"=="--foreground" set FOREGROUND=1
if /i "%~1"=="/foreground" set FOREGROUND=1
if /i "%~1"=="-f" set FOREGROUND=1
echo %~1| findstr "^[0-9][0-9]*$" >nul && set PORT=%~1
shift
goto parse_args
:done_args

:: 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found in your PATH!
    echo Please install Python 3.10 and ensure "Add Python to PATH" is checked.
    popd
    pause
    exit /b 1
)

:: 2. Check if already running on the target port
set ALREADY_RUNNING=0
for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    set ALREADY_RUNNING=%%p
)

if not "%ALREADY_RUNNING%"=="0" (
    echo [INFO] Kolam Drawing Studio is ALREADY RUNNING on port %PORT% - PID %ALREADY_RUNNING%.
    echo.
    echo   Local Host Access:  http://localhost:%PORT%
    if "%NO_BROWSER%"=="0" (
        echo   Opening browser...
        start http://localhost:%PORT%
    )
    echo.
    echo   To stop the server, run: stop.bat %PORT%
    echo ========================================================================
    popd
    ping 127.0.0.1 -n 3 >nul
    exit /b 0
)

:: 3. Discover primary LAN IPv4 address
set LAN_IP=
for /f "tokens=*" %%i in ('python -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(s.getsockname()[0]); s.close()" 2^>nul') do set LAN_IP=%%i
if "%LAN_IP%"=="" set LAN_IP=127.0.0.1

echo [NETWORK DISCOVERY]
echo   Local Host Access:      http://localhost:%PORT%
echo                           http://127.0.0.1:%PORT%
echo   LAN / Wi-Fi Access:     http://%LAN_IP%:%PORT%
echo.
echo ========================================================================
echo   HOW TO USE ON PHONE OR TABLET:
echo      1. Connect phone or tablet to the SAME Wi-Fi network as this PC.
echo      2. Open mobile browser and go to: http://%LAN_IP%:%PORT%
echo      3. Upload reference sketch, adjust opacity, and draw with touch/stylus!
echo.
echo   FIREWALL NOTE:
echo      If your mobile device cannot connect, run PowerShell as Administrator:
echo      New-NetFirewallRule -DisplayName "Kolam Studio Port %PORT%" -Direction Inbound -LocalPort %PORT% -Protocol TCP -Action Allow -Profile Private
echo.
echo   TO STOP THE SERVER:
echo      Run stop.bat or close the "Kolam Studio Server" window.
echo ========================================================================
echo.

:: 4. Launch web application
if "%FOREGROUND%"=="1" (
    if "%NO_BROWSER%"=="0" (
        start "" cmd /c "ping 127.0.0.1 -n 3 >nul & start http://localhost:%PORT%"
    )
    echo Starting Kolam Studio Server in foreground [Press Ctrl+C to stop]...
    python web_app.py --host 0.0.0.0 --port %PORT%
    popd
    exit /b %errorlevel%
)

echo Starting Kolam Studio Server in a background window...
start "Kolam Studio Server (Port %PORT%)" /D "%~dp0" cmd /k "python web_app.py --host 0.0.0.0 --port %PORT%"

:: 5. Wait for startup and save PID
echo Waiting for server startup...
ping 127.0.0.1 -n 4 >nul

del "%~dp0server.pid" 2>nul
for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    echo %%p > "%~dp0server.pid"
)

if "%NO_BROWSER%"=="0" (
    echo Opening http://localhost:%PORT% in your browser...
    start http://localhost:%PORT%
)

echo.
echo [SUCCESS] Kolam Studio is now online and ready on port %PORT%!
popd
ping 127.0.0.1 -n 3 >nul
exit /b 0
