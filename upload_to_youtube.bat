@echo off
setlocal enabledelayedexpansion

:: Force working directory to the location of this bat file
cd /d "%~dp0"

echo ===================================================
echo         AK Kolam - YouTube Uploader Tool
echo ===================================================
echo.

:: Check if a file was dragged and dropped onto this bat file
if not "%~1"=="" (
    set "TARGET_FILE=%~1"
    set "EXT=%~x1"
    echo [INFO] Detected input file: !TARGET_FILE!
    echo.

    if /i "!EXT!"==".txt" (
        echo [INFO] Uploading using metadata file...
        python -u upload_to_youtube.py --metadata "!TARGET_FILE!"
    ) else if /i "!EXT!"==".mp4" (
        echo [INFO] Uploading video file...
        python -u upload_to_youtube.py --video "!TARGET_FILE!"
    ) else (
        echo [WARNING] Unrecognized file type (!EXT!). Trying as metadata...
        python -u upload_to_youtube.py --metadata "!TARGET_FILE!"
    )
) else (
    echo [INFO] No file dragged. Scanning outputs\ folder for the latest video...
    echo.
    python -u upload_to_youtube.py
)

echo.
echo ===================================================
echo [INFO] Execution finished.
echo ===================================================
pause
