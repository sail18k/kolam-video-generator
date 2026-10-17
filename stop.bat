@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Stop Kolam Drawing Studio

echo ========================================================================
echo   [STOP] KOLAM VIDEO GENERATOR V2 - DRAWING STUDIO SERVER
echo ========================================================================
echo.

pushd "%~dp0." || exit /b 1
set "PORT=8000"
set "KOLAM_APP_SCRIPT=%~dp0web_app.py"
set "STOPPED=0"
set "PID_FILE_PID="
set "PID_FILE_PORT="

if not "%~1"=="" (
    echo(%~1| findstr /r /x "[0-9][0-9]*" >nul
    if errorlevel 1 (
        echo [ERROR] Port must be a number between 1 and 65535.
        popd
        exit /b 2
    )
    set "PORT=%~1"
)

powershell -NoProfile -Command "$p=0; if ([int]::TryParse($env:PORT,[ref]$p) -and $p -ge 1 -and $p -le 65535) { exit 0 } else { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Port must be a number between 1 and 65535.
    popd
    exit /b 2
)

:: A PID file is only a hint. The process command line must identify this app and port.
if exist "%~dp0server.pid" (
    for /f "usebackq tokens=1,2" %%p in ("%~dp0server.pid") do (
        set "PID_FILE_PID=%%p"
        set "PID_FILE_PORT=%%q"
    )
    if "!PID_FILE_PORT!"=="" set "PID_FILE_PORT=8000"
    if "!PID_FILE_PORT!"=="%PORT%" if not "!PID_FILE_PID!"=="" call :stop_if_kolam "!PID_FILE_PID!"
)

:: Also find the listener directly, in case the PID file is missing or stale.
for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    if not "%%p"=="" if not "%%p"=="0" if not "%%p"=="4" call :stop_if_kolam "%%p"
)

if "!STOPPED!"=="1" (
    :: The title is assigned by start.bat; close only this port's server console.
    taskkill /fi "WINDOWTITLE eq Kolam Studio Server (Port %PORT%)" /f /t >nul 2>&1
)

if "!PID_FILE_PORT!"=="%PORT%" if exist "%~dp0server.pid" del /f /q "%~dp0server.pid" >nul 2>&1

:: Give Windows a moment to release the listener before reporting status.
ping 127.0.0.1 -n 2 >nul
set "PORT_STILL_ACTIVE=0"
for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    if not "%%p"=="" if not "%%p"=="0" if not "%%p"=="4" set "PORT_STILL_ACTIVE=%%p"
)

echo.
if "!PORT_STILL_ACTIVE!"=="0" (
    if "!STOPPED!"=="1" (
        echo ========================================================================
        echo   [SUCCESS] Kolam Drawing Studio stopped. Port %PORT% is free.
        echo ========================================================================
    ) else (
        echo ========================================================================
        echo   [INFO] No Kolam Drawing Studio server was found on port %PORT%.
        echo ========================================================================
    )
) else (
    echo ========================================================================
    if "!STOPPED!"=="1" (
        echo   [WARNING] Kolam stopped, but port %PORT% is still held by PID !PORT_STILL_ACTIVE!.
    ) else (
        echo   [WARNING] Port %PORT% is held by PID !PORT_STILL_ACTIVE!, which was not identified as this app.
        echo             No unrelated process was terminated.
    )
    echo ========================================================================
)

popd
exit /b 0

:stop_if_kolam
set "CANDIDATE_PID=%~1"
if not defined CANDIDATE_PID exit /b 0
powershell -NoProfile -Command "$p=Get-CimInstance Win32_Process -Filter 'ProcessId = %CANDIDATE_PID%' -ErrorAction SilentlyContinue; $script=[IO.Path]::GetFullPath($env:KOLAM_APP_SCRIPT); $isApp=$p -and $p.CommandLine -and ($p.CommandLine.IndexOf($script,[StringComparison]::OrdinalIgnoreCase) -ge 0 -or [regex]::IsMatch($p.CommandLine,'(?i)(?:^|\s)web_app\.py(?:\s|$)')); if ($isApp -and [regex]::IsMatch($p.CommandLine,'(?i)(?:^|\s)--port\s+%PORT%(?:\s|$)')) { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; exit 0 } else { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo [OK] Terminated Kolam server process PID %CANDIDATE_PID% on port %PORT%.
    set "STOPPED=1"
)
exit /b 0
