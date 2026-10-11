@echo off
setlocal enabledelayedexpansion

:: Force working directory to the location of this bat file
cd /d "%~dp0"

echo ===================================================
echo         AK Kolam - YouTube Uploader Tool
echo ===================================================
echo.

if "%~1"=="" goto :no_args

:: A file was dragged and dropped
set "TARGET_FILE=%~1"
set "EXT=%~x1"
echo [INFO] Detected input file: %TARGET_FILE%
echo.

if /i "%EXT%"==".txt" (
    echo [INFO] Uploading using metadata file...
    python -u upload_to_youtube.py --metadata "%TARGET_FILE%"
    goto :done
)

if /i "%EXT%"==".mp4" (
    echo [INFO] Uploading video file...
    python -u upload_to_youtube.py --video "%TARGET_FILE%"
    goto :done
)

echo [WARNING] Unrecognized file type (%EXT%). Trying as metadata...
python -u upload_to_youtube.py --metadata "%TARGET_FILE%"
goto :done

:no_args
echo [INFO] Scanning outputs\ folder for the latest generated video...
echo.
python -u upload_to_youtube.py

:done
echo.
echo ===================================================
echo [INFO] Process completed.
echo ===================================================
pause
