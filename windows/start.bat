@echo off
setlocal
title Minecraft Paper 26.2 + Geyser

REM Always run from the folder this .bat lives in. Keeping the working
REM directory out of Documents also matters: Controlled Folder Access blocks
REM writes there, which makes wrangler hang and the server die silently.
cd /d "%~dp0"

REM ---- settings ----
REM Xms is a floor, not a starting point: the JVM never hands back memory
REM below it. Keeping it low lets an idle server shrink toward its real live
REM set (~350 MB here) instead of sitting on 2 GB.
set "MIN_RAM=1G"
set "MAX_RAM=4G"

REM Periodic GC while idle, then shrink and return the pages to Windows.
REM This is the right way to "reclaim memory on a timer" - forcing GC from a
REM scheduled command would stall the server and not uncommit anything.
set "GC_OPTS=-XX:+UseG1GC -XX:G1PeriodicGCInterval=300000 -XX:MinHeapFreeRatio=10 -XX:MaxHeapFreeRatio=25"
set "JAR=paper.jar"
set "SYNC_MINUTES=30"
REM ------------------

REM Called by the Discord control bot as: start.bat /nopause
REM Without this the final PAUSE would leave an invisible cmd process
REM waiting on a keypress nobody can give it.
set "NOPAUSE="
if /i "%~1"=="/nopause" set "NOPAUSE=1"

where java >nul 2>&1
if errorlevel 1 (
    echo [ERROR] java not found in PATH.
    if not defined NOPAUSE pause
    exit /b 1
)

if not exist "%JAR%" (
    echo [ERROR] %JAR% not found in %CD%
    if not defined NOPAUSE pause
    exit /b 1
)

netstat -ano | findstr /c:"LISTENING" | findstr /c:":25565 " >nul
if not errorlevel 1 (
    echo [WARN] Port 25565 already in use - server may already be running.
    echo        Type "stop" in the existing server window before restarting.
    if not defined NOPAUSE pause
    exit /b 1
)

echo ============================================================
echo  Starting playit tunnel agent...
echo ============================================================
sc start playitd >nul 2>&1
if errorlevel 1 (
    echo [WARN] Could not start the playit service - it may already be running.
) else (
    echo playit service started.
)

echo.
echo ============================================================
echo  Starting BlueMap map sync (every %SYNC_MINUTES% min)...
echo ============================================================
start "bluemap-sync" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-loop.ps1" -IntervalMinutes %SYNC_MINUTES%

echo.
echo ============================================================
echo  Starting Paper %MIN_RAM%-%MAX_RAM%
echo  Java 25565 ^| Bedrock UDP 19132 ^| Map http://localhost:8100
echo.
echo  Type "stop" in this window to shut down cleanly.
echo  Do NOT just close the window.
echo ============================================================
echo.

REM Marker for watchdog.ps1: the server is meant to be running. The
REM cleanup below removes it on a deliberate stop, so an unexpected
REM death leaves it behind and the watchdog knows to restart.
echo %DATE% %TIME% > "%~dp0server.running"

java -Xms%MIN_RAM% -Xmx%MAX_RAM% %GC_OPTS% -jar "%JAR%" nogui
set "EXITCODE=%errorlevel%"

echo.
echo Server stopped ^(exit code %EXITCODE%^).

REM Exit code tells deliberate from unexpected: a clean "stop" returns 0,
REM while a crash or a killed process does not. On an unexpected death we
REM leave the marker and the tunnel alone so watchdog.ps1 can restart the
REM server without a teardown/setup cycle in between.
if not "%EXITCODE%"=="0" (
    echo [WARN] Unexpected exit - leaving the tunnel up for the watchdog.
    powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.CommandLine -like '*sync-loop*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
    goto :done
)

REM A newer start.bat may already have taken over while this one was still
REM saving the world - restarting quickly used to make this instance tear down
REM the services the new one had just started. If port 25565 is listening
REM again, the new instance owns playit and the sync loop: leave them alone.
REM Look for a java process running paper.jar rather than a listening port:
REM a new instance starts playit about 40 seconds before its port binds, and
REM checking the port let this cleanup stop the tunnel during that window.
powershell.exe -NoProfile -Command "if (Get-CimInstance Win32_Process -Filter \"Name='java.exe'\" | Where-Object { $_.CommandLine -like '*paper.jar*' }) { exit 1 } else { exit 0 }" >nul 2>&1
if errorlevel 1 (
    echo Another server instance is already running - skipping cleanup.
    goto :done
)

REM Deliberate shutdown: clear the marker so the watchdog leaves it alone.
del "%~dp0server.running" >nul 2>&1

echo Cleaning up...

REM Stop the sync loop we started above. Match on the command line rather
REM than the window title: Windows prefixes the title with "Select"/"choose"
REM whenever the console is in selection mode, which breaks title matching.
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | Where-Object { $_.CommandLine -like '*sync-loop*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

REM One final sync so the published map matches the world we just saved.
echo Running a final map sync...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync-map.ps1"

echo Stopping playit tunnel agent...
sc stop playitd >nul 2>&1

echo.
echo All stopped.

:done
if not defined NOPAUSE pause
