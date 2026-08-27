#!/usr/bin/env python3
"""Scheduled restart: warn, count down, restart.

Launched 5 minutes before the intended restart time. Announces at 5, 3 and 1
minutes, counts down the last 30 seconds, saves, stops, then brings the server
back up with start.bat.

This replaced a PowerShell version that opened a fresh RCON connection per
announcement. That cost a process spawn plus a TCP connect and auth every
time, which both drifted the one-second countdown and silently lost an
announcement when a connection was refused. Here one session stays open for
the whole sequence, every step is retried, and each step sleeps until an
absolute deadline so a slow command cannot push the rest of the countdown late.

Usage:
    python restart-sequence.py
    python restart-sequence.py --dry-run              (announce only)
    python restart-sequence.py --dry-run --compress 60  (fast rehearsal)
"""

import argparse
import datetime
import json
import os
import socket
import subprocess
import sys
import time

import rcon

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(HERE, 'scheduled-restart.log')
START_BAT = os.path.join(HERE, 'start.bat')
# watchdog.ps1 restarts the server whenever start.bat's "server.running"
# marker is present but no java process is. For about two seconds after a
# deliberate stop both of those are true, and a watchdog tick landing there
# would launch a second start.bat alongside this one: the port is still free,
# so both pass start.bat's guard, and the loser's java dies unable to bind.
# This lock tells the watchdog a restart is already in hand.
LOCK_PATH = os.path.join(HERE, 'restart.lock')
GAME_PORT = 25565

# Seconds before the restart, and what to say at that point. The action bar is
# what players actually notice; chat carries the detail.
SCHEDULE = [
    (300, '伺服器將在 5 分鐘後重啟（{reason}）', '5 分鐘後重啟'),
    (180, '伺服器將在 3 分鐘後重啟', '3 分鐘後重啟'),
    (60, '伺服器將在 1 分鐘後重啟，請找安全的地方登出', '1 分鐘後重啟'),
    (30, '重啟倒數 30 秒', '重啟倒數 30'),
    (20, '重啟倒數 20 秒', '重啟倒數 20'),
    (10, '重啟倒數 10 秒', '重啟倒數 10'),
    (5, '重啟倒數 5', '5'),
    (4, '重啟倒數 4', '4'),
    (3, '重啟倒數 3', '3'),
    (2, '重啟倒數 2', '2'),
    (1, '重啟倒數 1', '1'),
]

LEAD_SECONDS = SCHEDULE[0][0]


def log(message, level='INFO'):
    line = '{0} [{1}] {2}'.format(
        datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), level, message)
    print(line, flush=True)
    try:
        # Keep the log from growing without bound; this runs twice a day.
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 512 * 1024:
            with open(LOG_PATH, encoding='utf-8', errors='replace') as fh:
                tail = fh.readlines()[-200:]
            with open(LOG_PATH, 'w', encoding='utf-8') as fh:
                fh.writelines(tail)
        with open(LOG_PATH, 'a', encoding='utf-8') as fh:
            fh.write(line + chr(10))
    except OSError:
        pass


def take_lock():
    with open(LOCK_PATH, 'w', encoding='utf-8') as fh:
        fh.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + chr(10))


def release_lock():
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


def server_process_running():
    """True if a java process is running paper.jar.

    Used as a second guard before launching: if a watchdog tick beat us to it
    despite the lock, starting another start.bat would leave one of the two
    JVMs unable to bind the port.
    """
    try:
        out = subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command',
             "if (Get-CimInstance Win32_Process -Filter \"Name='java.exe'\" | "
             "Where-Object { $_.CommandLine -like '*paper.jar*' }) "
             "{ 'yes' } else { 'no' }"],
            capture_output=True, text=True, timeout=30,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return 'yes' in out.stdout
    except Exception:
        # Never block a restart on this check failing.
        return False


def port_open(port, host='127.0.0.1', timeout=2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


class Session:
    """One RCON connection, reopened on demand.

    A dropped announcement is the failure that matters here: players who never
    saw a warning are the whole reason this script exists. So every command is
    retried on a fresh connection rather than being logged and forgotten.
    """

    def __init__(self):
        self.props = rcon.load_props()
        self.sock = None
        self.req = 1

    def _connect(self):
        host = self.props.get('server-ip') or '127.0.0.1'
        port = int(self.props.get('rcon.port', 25575))
        password = self.props.get('rcon.password', '')
        if self.props.get('enable-rcon', 'false') != 'true':
            raise RuntimeError('enable-rcon is not true in server.properties')
        if not password:
            raise RuntimeError('rcon.password is empty')

        sock = socket.create_connection((host, port), timeout=8)
        sock.sendall(rcon.pack(1, 3, password))
        req_id, _, _ = rcon.read_packet(sock)
        if req_id == -1:
            sock.close()
            raise RuntimeError('RCON 認證失敗（密碼不符）')
        self.sock = sock

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def _send(self, command):
        self.req += 1
        sentinel = 9999
        self.sock.sendall(rcon.pack(self.req, 2, command))
        self.sock.sendall(rcon.pack(sentinel, 2, ''))
        chunks = []
        while True:
            rid, _, body = rcon.read_packet(self.sock)
            if rid == sentinel:
                break
            chunks.append(body)
        return rcon.strip_colors(''.join(chunks)).strip()

    def run(self, command, attempts=3):
        last = ''
        for attempt in range(attempts):
            try:
                if self.sock is None:
                    self._connect()
                return True, self._send(command)
            except Exception as exc:
                last = '{0}: {1}'.format(type(exc).__name__, exc)
                self.close()
                if attempt + 1 < attempts:
                    time.sleep(0.4)
        return False, last


def announce(session, chat, action_bar):
    ok, detail = session.run('say ' + chat)
    if not ok:
        log('announce failed: {0} ({1})'.format(chat, detail), 'ERROR')
    else:
        log('announce: ' + chat)
    if action_bar:
        component = json.dumps(
            {'text': action_bar, 'color': 'gold', 'bold': True},
            ensure_ascii=False)
        session.run('title @a actionbar ' + component)
    return ok


def wait_until(deadline):
    remaining = deadline - time.monotonic()
    if remaining > 0:
        time.sleep(remaining)


def stop_server(session):
    session.run('save-all')
    ok, detail = session.run('stop')
    log('stop issued: {0}'.format(detail.replace(chr(10), ' | ')))
    session.close()

    for _ in range(40):
        time.sleep(3)
        if not port_open(GAME_PORT):
            log('Server stopped')
            return True
    return ok and False


def start_server():
    if server_process_running():
        log('A server process is already running - not starting a second one',
            'WARN')
        return port_open(GAME_PORT) or wait_for_port()

    # start.bat brings the playit tunnel and the map sync back up as well.
    subprocess.Popen(
        ['cmd.exe', '/c', 'start', 'MC Server', '/min', START_BAT, '/nopause'],
        cwd=HERE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return wait_for_port()


def wait_for_port(tries=60):
    for _ in range(tries):
        time.sleep(3)
        if port_open(GAME_PORT):
            log('Server is back up')
            return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true',
                        help='announce the whole sequence but do not restart')
    parser.add_argument('--compress', type=int, default=1,
                        help='divide every wait by this; 1 = real timing')
    parser.add_argument('--reason', default='定期重啟以釋放記憶體')
    args = parser.parse_args()

    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    if not port_open(GAME_PORT):
        log('Server is not running - nothing to restart')
        return 0

    compress = max(1, args.compress)
    log('Restart sequence started (dry run: {0}, compress: {1}x)'.format(
        args.dry_run, compress))

    # Absolute deadlines from a single origin, so a slow command eats into its
    # own slot instead of pushing every later announcement back.
    origin = time.monotonic()
    session = Session()

    try:
        for before, chat, action_bar in SCHEDULE:
            wait_until(origin + (LEAD_SECONDS - before) / compress)
            announce(session, chat.format(reason=args.reason), action_bar)

        wait_until(origin + LEAD_SECONDS / compress)

        if args.dry_run:
            announce(session, '（演練）這裡就會重啟，實際上不會', None)
            log('Dry run: stopping here')
            return 0

        announce(session, '伺服器重啟中，約 40 秒後回來', '重啟中')

        take_lock()
        if not stop_server(session):
            log('Server did not stop within 2 minutes - '
                'not starting a second one', 'ERROR')
            return 1

        if not start_server():
            log('Server did not come back within 3 minutes', 'ERROR')
            return 1
        return 0
    finally:
        session.close()
        release_lock()


if __name__ == '__main__':
    sys.exit(main())
