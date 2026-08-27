@echo off
REM Starts the LAN-only monitoring console.
REM Keep the working directory here: check-server.py and rcon.py are loaded
REM as siblings, and Controlled Folder Access blocks writes under Documents.
cd /d "%~dp0"
title Minecraft Web Console
python web-console.py %*
if errorlevel 1 pause
