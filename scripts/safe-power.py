#!/usr/bin/env python3
"""Desktop shortcuts "安全重開電腦" and "安全關機".

Restarting or shutting down Windows while the server runs kills java without
saving the world (it happened on 2026-10-25). These stop the server the
planned way first - restart-sequence.py --stop, so anyone online gets the
5-minute countdown - wait until java has finished saving, and only then
restart or shut down Windows.

The server.running marker is put back before Windows goes down, so the
watchdog starts the server again within 5 minutes of the next logon.

Usage:  pythonw safe-power.py --reboot
        pythonw safe-power.py --shutdown
"""
import argparse
import ctypes
import datetime
import importlib.util
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SEQUENCE = os.path.join(HERE, 'restart-sequence.py')

_spec = importlib.util.spec_from_file_location('restart_sequence', SEQUENCE)
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)

MARKER = os.path.join(rs.SERVER_DIR, 'server.running')
TITLE = 'Minecraft 伺服器'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
GRACE = 30      # seconds Windows waits; "shutdown /a" calls it off


def ask(text):
    # MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2: "No" is the default button.
    return ctypes.windll.user32.MessageBoxW(None, text, TITLE, 0x4 | 0x20 | 0x100) == 6


def tell(text, icon=0x40):
    ctypes.windll.user32.MessageBoxW(None, text, TITLE, icon)


def wait_for(condition, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(2)
    return condition()


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--reboot', action='store_true')
    mode.add_argument('--shutdown', action='store_true')
    args = parser.parse_args()
    verb = '重新開機' if args.reboot else '關機'

    running = rs.server_process_running() or rs.port_open(rs.GAME_PORT)
    text = '確定要讓電腦%s嗎？\n\n' % verb
    if running:
        text += ('會先照伺服器規則關服：有人在線上就先倒數 5 分鐘，沒人就立刻關。'
                 '世界存好檔後電腦才會%s。\n\n下次登入 Windows 後，'
                 '伺服器會在 5 分鐘內自動開回來。' % verb)
    if not ask(text):
        return 0

    if running:
        rs.log('safe-power: stopping the server before Windows %s' % ('restarts' if args.reboot else 'shuts down'))
        subprocess.run([sys.executable, SEQUENCE, '--stop', '--by', 'safe-power',
                        '--reason', '電腦%s' % verb], cwd=HERE, creationflags=NO_WINDOW)
        if rs.port_open(rs.GAME_PORT):
            tell('關服倒數被取消了，電腦不會%s。' % verb, 0x30)
            return 1
        # The port closes before the world is saved; java exiting is the
        # signal that saving is done. Big saves have taken minutes here.
        if not wait_for(lambda: not rs.server_process_running(), 15 * 60):
            tell('伺服器 15 分鐘內沒有結束，電腦不會%s。請看 logs\\latest.log。' % verb, 0x10)
            return 1
        # start.bat deletes the marker after a clean stop; let it, then put
        # it back so the watchdog brings the server up after the next logon.
        # The fresh lock keeps the watchdog from starting it again in the
        # seconds before Windows goes down (it ignores locks from before boot).
        wait_for(lambda: not os.path.exists(MARKER), 60)
        rs.take_lock()
        with open(MARKER, 'w', encoding='ascii') as fh:
            fh.write('planned-power %s\n' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        rs.log('safe-power: server stopped and saved; Windows %s in %d s'
               % ('restarts' if args.reboot else 'shuts down', GRACE))

    subprocess.run(['shutdown', '/r' if args.reboot else '/s', '/t', str(GRACE),
                    '/c', 'Minecraft 伺服器已安全關閉，%d 秒後%s。' % (GRACE, verb)],
                   creationflags=NO_WINDOW)
    return 0


if __name__ == '__main__':
    sys.exit(main())
