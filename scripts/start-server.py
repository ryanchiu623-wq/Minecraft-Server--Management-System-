#!/usr/bin/env python3
"""Desktop shortcut "啟動 Minecraft 伺服器": start the server with no window.

The server used to start in a console window, and closing that window kills
java without saving. This starts it the way every other launcher does
(settings.server_launch_command) and says so in a message box, since there is
no window to watch.

Usage:  pythonw start-server.py
"""
import ctypes
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import settings  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    'restart_sequence', os.path.join(HERE, 'restart-sequence.py'))
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

TITLE = 'Minecraft 伺服器'


def message(text, icon=0x40):
    ctypes.windll.user32.MessageBoxW(None, text, TITLE, icon)


def main():
    # The java process, not the port: the port only opens about a minute after
    # start, and a second double-click in that minute must not start another.
    if rs.server_process_running() or rs.port_open(rs.GAME_PORT):
        message('伺服器已經在執行中。')
        return 0
    subprocess.Popen(settings.server_launch_command(rs.START_BAT), cwd=rs.SERVER_DIR,
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    message('伺服器啟動中，大約 1 分鐘後就能連線。\n\n'
            '伺服器現在沒有視窗：狀態和主控台請看網頁管理台或 Discord 機器人，'
            '關服請用它們的「關閉」，或遊戲裡的 /serverctl stop。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
