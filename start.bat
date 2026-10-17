@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Kolam Interactive Drawing Studio - Starter

echo ========================================================================
echo   [START] KOLAM VIDEO GENERATOR V2 - INTERACTIVE DRAWING STUDIO
echo ========================================================================
echo.

pushd "%~dp0." || exit /b 1

set "PORT=8000"
set "NO_BROWSER=0"
set "FOREGROUND=0"
set "DRAWING_SPEED=1.2"
set "KOLAM_APP_SCRIPT=%~dp0web_app.py"

:parse_args
if "%~1"=="" goto done_args
if /i "%~1"=="--help" goto show_help
if /i "%~1"=="-h" goto show_help
if /i "%~1"=="/?" goto show_help
if /i "%~1"=="--no-browser" (set "NO_BROWSER=1" & shift & goto parse_args)
if /i "%~1"=="/nobrowser" (set "NO_BROWSER=1" & shift & goto parse_args)
if /i "%~1"=="-n" (set "NO_BROWSER=1" & shift & goto parse_args)
if /i "%~1"=="--foreground" (set "FOREGROUND=1" & shift & goto parse_args)
if /i "%~1"=="/foreground" (set "FOREGROUND=1" & shift & goto parse_args)
if /i "%~1"=="-f" (set "FOREGROUND=1" & shift & goto parse_args)
if /i "%~1"=="--speed" goto read_speed
if /i "%~1"=="-s" goto read_speed
echo(%~1| findstr /r /x "[0-9][0-9]*" >nul
if not errorlevel 1 (
    set "PORT=%~1"
    shift
    goto parse_args
)
echo [ERROR] Unknown option: %~1
goto show_help_error

:read_speed
if "%~2"=="" (
    echo [ERROR] --speed requires a multiplier, for example: --speed 1.2
    goto show_help_error
)
set "DRAWING_SPEED=%~2"
shift
shift
goto parse_args

:show_help
echo Usage: start.bat [PORT] [--no-browser] [--foreground] [--speed MULTIPLIER]
echo.
echo Options:
echo   PORT           Port to run the server on (default: 8000)
echo   --no-browser   Do not automatically open the default web browser (-n)
echo   --foreground   Run the server in the current window (-f)
echo   --speed        Default hand drawing speed multiplier (default: 1.2) (-s)
echo   --help, -h     Show this help message
echo.
echo Examples:
echo   start.bat
echo   start.bat 8080
echo   start.bat --foreground
echo   start.bat 8000 --speed 1.5
popd
exit /b 0

:show_help_error
echo.
echo Usage: start.bat [PORT] [--no-browser] [--foreground] [--speed MULTIPLIER]
pause
popd
exit /b 2

:done_args

:: Validate the port before using it in netstat or the Python command line.
echo(%PORT%| findstr /r /x "[0-9][0-9]*" >nul
if errorlevel 1 (
    echo [ERROR] Port must be a number between 1 and 65535.
    pause
    popd
    exit /b 2
)
powershell -NoProfile -Command "$p=0; if ([int]::TryParse($env:PORT,[ref]$p) -and $p -ge 1 -and $p -le 65535) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Port must be a number between 1 and 65535.
    pause
    popd
    exit /b 2
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found in your PATH.
    echo Please install Python 3.10 or newer and ensure "Add Python to PATH" is checked.
    popd
    pause
    exit /b 1
)

:: Distinguish this app from an unrelated process using the requested port.
set "PORT_IN_USE=0"
set "PORT_IN_USE_PID="
set "ALREADY_RUNNING=0"
for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    if not "%%p"=="" if not "%%p"=="0" if not "%%p"=="4" (
        set "PORT_IN_USE=1"
        set "PORT_IN_USE_PID=%%p"
        powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process -Filter 'ProcessId = %%p' -ErrorAction SilentlyContinue; $script=[IO.Path]::GetFullPath($env:KOLAM_APP_SCRIPT); $isApp=$p -and $p.CommandLine -and ($p.CommandLine.IndexOf($script,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or [regex]::IsMatch($p.CommandLine,'(?i)(?:^|\s)web_app\.py(?:\s|$)')); if ($isApp -and [regex]::IsMatch($p.CommandLine,'(?i)(?:^|\s)--port\s+%PORT%(?:\s|$)')) { exit 0 } else { exit 1 }" >nul 2>&1
        if not errorlevel 1 set "ALREADY_RUNNING=%%p"
    )
)

if not "%ALREADY_RUNNING%"=="0" (
    (echo %ALREADY_RUNNING% %PORT%)>"%~dp0server.pid"
    echo [INFO] Kolam Drawing Studio is already running on port %PORT% - PID %ALREADY_RUNNING%.
    echo.
    echo   Local: http://localhost:%PORT%
    if "%NO_BROWSER%"=="0" start "" "http://localhost:%PORT%"
    echo   To stop it, run: stop.bat %PORT%
    echo.
    echo Press any key to close this launcher. The server will keep running.
    pause >nul
    popd
    exit /b 0
)

if "%PORT_IN_USE%"=="1" (
    echo [ERROR] Port %PORT% is already used by another process. PID: %PORT_IN_USE_PID%.
    echo         Stop that application or choose another port.
    pause
    popd
    exit /b 1
)

set "LAN_IP="
for /f "tokens=*" %%i in ('python -c "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('8.8.8.8', 80)); print(s.getsockname()[0]); s.close()" 2^>nul') do set "LAN_IP=%%i"
if "%LAN_IP%"=="" set "LAN_IP=127.0.0.1"

echo [NETWORK DISCOVERY]
echo   Local Host Access:      http://localhost:%PORT%
echo                           http://127.0.0.1:%PORT%
echo   LAN / Wi-Fi Access:     http://%LAN_IP%:%PORT%
echo   Drawing Speed:          %DRAWING_SPEED%x
echo.
echo ========================================================================
echo   PHONE OR TABLET ACCESS:
echo      Connect to the same Wi-Fi network and open http://%LAN_IP%:%PORT%
echo.
echo   FIREWALL NOTE:
echo      If the phone cannot connect, allow TCP port %PORT% on the Private profile.
echo      PowerShell command (run as Administrator):
echo      New-NetFirewallRule -DisplayName "Kolam Studio Port %PORT%" -Direction Inbound -LocalPort %PORT% -Protocol TCP -Action Allow -Profile Private
echo.
echo   To stop the server, run: stop.bat %PORT%
echo ========================================================================
echo.

if "%FOREGROUND%"=="1" (
    if "%NO_BROWSER%"=="0" start "" cmd /c "ping 127.0.0.1 -n 3 >nul & start http://localhost:%PORT%"
    echo Starting Kolam Studio Server in foreground. Press Ctrl+C to stop.
    python -u "%KOLAM_APP_SCRIPT%" --host 0.0.0.0 --port %PORT% --drawing-speed %DRAWING_SPEED%
    set "EXIT_CODE=!ERRORLEVEL!"
    popd
    exit /b !EXIT_CODE!
)

if exist "%~dp0server.pid" del /f /q "%~dp0server.pid" >nul 2>&1
echo Starting Kolam Studio Server in a background window...
start "Kolam Studio Server (Port %PORT%)" /D "%~dp0." cmd /d /k python -u web_app.py --host 0.0.0.0 --port %PORT% --drawing-speed %DRAWING_SPEED%

echo Waiting for server startup...
set "SERVER_STARTED=0"
set "SERVER_PID="
for /L %%i in (1,1,15) do (
    if "!SERVER_STARTED!"=="0" (
        ping 127.0.0.1 -n 2 >nul
        for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
            if not "%%p"=="" if not "%%p"=="0" if not "%%p"=="4" (
                powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process -Filter 'ProcessId = %%p' -ErrorAction SilentlyContinue; $script=[IO.Path]::GetFullPath($env:KOLAM_APP_SCRIPT); $isApp=$p -and $p.CommandLine -and ($p.CommandLine.IndexOf($script,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or [regex]::IsMatch($p.CommandLine,'(?i)(?:^|\s)web_app\.py(?:\s|$)')); if ($isApp -and [regex]::IsMatch($p.CommandLine,'(?i)(?:^|\s)--port\s+%PORT%(?:\s|$)')) { exit 0 } else { exit 1 }" >nul 2>&1
                if not errorlevel 1 (
                    set "SERVER_STARTED=1"
                    set "SERVER_PID=%%p"
                    (echo %%p %PORT%)>"%~dp0server.pid"
                )
            )
        )
    )
)

if "!SERVER_STARTED!"=="1" (
    if "%NO_BROWSER%"=="0" (
        echo Opening http://localhost:%PORT% in your browser...
        start "" "http://localhost:%PORT%"
    )
    echo.
    echo ========================================================================
    echo   [SUCCESS] Kolam Studio is online on port %PORT% - PID !SERVER_PID!
    echo   Local: http://localhost:%PORT%
    echo   LAN:   http://%LAN_IP%:%PORT%
    echo   To stop it, run: stop.bat %PORT%
    echo ========================================================================
    echo.
    echo Press any key to close this launcher. The server window will keep running.
    pause >nul
    popd
    exit /b 0
)

echo.
echo ========================================================================
echo   [ERROR] Kolam Studio did not start on port %PORT% within 15 seconds.
echo   Inspect the "Kolam Studio Server" window for Python errors.
echo   Run "start.bat --foreground" to see errors in this window.
echo ========================================================================
popd
pause
exit /b 1
