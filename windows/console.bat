@echo off
REM Desktop console for the Minecraft server.
REM pythonw keeps the black console window from appearing behind the GUI.
cd /d "%~dp0"
start "" pythonw.exe "%~dp0console-gui.py"
