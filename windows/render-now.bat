@echo off
setlocal
title BlueMap render and upload

REM Run from this folder. wrangler writes temp files into the working
REM directory, and anything under Documents gets blocked by Controlled
REM Folder Access - which hangs the upload with no error.
cd /d "%~dp0"

echo ============================================================
echo  1/3  Asking BlueMap to re-render every map
echo ============================================================
python rcon.py "bluemap update overworld" "bluemap update world" "bluemap update world_the_end"
if errorlevel 1 (
    echo [ERROR] RCON failed - is the server running?
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  2/3  Waiting for the render threads to go idle
echo ============================================================
set /a TRIES=0
:waitloop
set /a TRIES+=1
if %TRIES% gtr 40 (
    echo [WARN] Still rendering after 7 minutes - not uploading.
    echo        Check progress with: python rcon.py "bluemap"
    pause
    exit /b 1
)
timeout /t 10 /nobreak >nul
python rcon.py "bluemap" | findstr /c:"render-threads are idle" >nul
if errorlevel 1 (
    echo   still rendering... ^(%TRIES%^)
    goto waitloop
)
echo   render finished.

echo.
echo ============================================================
echo  3/3  Uploading to Cloudflare Pages
echo ============================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-map.ps1"

echo.
echo Done. See mapUrl in config.json for the published address.
pause
