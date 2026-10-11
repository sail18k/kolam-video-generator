@echo off
setlocal enabledelayedexpansion

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

python generate.py --input "%INPUT_FILE%" --type auto

echo.
echo ===================================================
echo [INFO] Process completed! Check the outputs\ folder.
echo ===================================================
pause
