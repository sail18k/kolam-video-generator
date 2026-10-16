@echo off
title Stop Kolam Drawing Studio

echo ========================================================================
echo   [STOP] KOLAM VIDEO GENERATOR V2 - DRAWING STUDIO SERVER
echo ========================================================================
echo.

pushd "%~dp0."
set STOPPED=0

:: Optional port argument (default: 8000)
set PORT=8000
if not "%~1"=="" (
    echo %~1| findstr "^[0-9][0-9]*$" >nul && set PORT=%~1
)

:: 1. Try reading saved PID file and terminate process tree
if exist "server.pid" (
    for /f "tokens=*" %%p in (server.pid) do (
        if not "%%p"=="" (
            taskkill /f /t /pid %%p >nul 2>&1
            if not errorlevel 1 (
                echo [OK] Terminated server process tree with PID %%p
                set STOPPED=1
            )
        )
    )
    del /f /q "server.pid" >nul 2>&1
)

:: 2. Find and terminate any process listening on the target port
for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    if not "%%p"=="" (
        taskkill /f /t /pid %%p >nul 2>&1
        if not errorlevel 1 (
            echo [OK] Terminated process on port %PORT% - PID %%p
            set STOPPED=1
        )
    )
)

:: 3. Close any dedicated console window titled "Kolam Studio Server*"
taskkill /f /fi "WINDOWTITLE eq Kolam Studio Server*" >nul 2>&1
if not errorlevel 1 set STOPPED=1

echo.
if "%STOPPED%"=="1" (
    echo ========================================================================
    echo   [SUCCESS] Kolam Drawing Studio server has been stopped. Port %PORT% freed.
    echo ========================================================================
) else (
    echo ========================================================================
    echo   [INFO] No running Kolam Drawing Studio server was found on port %PORT%.
    echo ========================================================================
)

popd
echo.
ping 127.0.0.1 -n 3 >nul
exit /b 0
