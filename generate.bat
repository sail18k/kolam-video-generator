@echo off
setlocal enabledelayedexpansion

:: Force working directory to the location of this bat file
cd /d "%~dp0"

echo ===================================================
echo        Kolam Video Generator - Auto Setup
echo ===================================================

:: If an argument is provided (e.g. via drag and drop), use it
if "%~1"=="" (
    echo [INFO] No image dragged/dropped. Looking for images in inputs\ folder...
    set "INPUT_FILE="
    
    :: Find the first image in inputs
    for %%f in (inputs\*.jpg inputs\*.png inputs\*.jpeg) do (
        set "INPUT_FILE=%%f"
        goto :found
    )
    
    echo [ERROR] No images found in inputs\ folder. 
    echo Please place an image there or drag and drop an image onto this bat file.
    pause
    exit /b
) else (
    set "INPUT_FILE=%~1"
)

:found
echo [INFO] Using input image: %INPUT_FILE%
echo [INFO] Starting automatic setup and generation...
echo.

:: 1. Run video generation, natural coloring thumbnail, and dynamic SEO metadata
python -u generate.py --input "%INPUT_FILE%" --type auto --no-upload

if errorlevel 1 (
    echo.
    echo ===================================================
    echo [ERROR] Video generation failed. Please check the logs above.
    echo ===================================================
    pause
    exit /b %errorlevel%
)

:: 2. Interactive YouTube Upload Prompt
echo.
echo ===================================================
echo              YOUTUBE UPLOAD (Auto-Publish)
echo ===================================================
set "DO_UPLOAD="
set /p "DO_UPLOAD=Do you want to upload and publish this video to YouTube? (y/n) [default: n]: "

if /i "!DO_UPLOAD!"=="y" (
    echo.
    echo [INFO] Uploading video and thumbnail to YouTube...
    python -u upload_to_youtube.py --yes
) else (
    echo.
    echo [INFO] YouTube upload skipped.
    echo [INFO] You can upload anytime later by running: upload_to_youtube.bat
)

echo.
echo ===================================================
echo [INFO] Process completed! Check the outputs\ folder.
echo ===================================================
pause
