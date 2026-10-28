#!/usr/bin/env python3
"""Planned restart or shutdown: warn, count down, then act.

The published server rules promise players a 5-minute warning before any
planned restart, so every way of stopping the server on purpose - the web
console, the desktop console, the Discord bot - goes through this script.

Announces at 5, 3 and 1 minutes, counts down the last 30 seconds, saves,
stops, and (unless --stop) brings the server back up with start.bat. With
nobody online there is no one to warn, so it acts straight away.

While it runs it leaves restart.pending in the server folder (mode, deadline,
pid) so the consoles can show the countdown and refuse to start a second one.
Creating restart.cancel there - or running with --cancel - calls it off.

This replaced a PowerShell version that opened a fresh RCON connection per
announcement. That cost a process spawn plus a TCP connect and auth every
time, which both drifted the one-second countdown and silently lost an
announcement when a connection was refused. Here one session stays open for
the whole sequence, every step is retried, and each step sleeps until an
absolute deadline so a slow command cannot push the rest of the countdown late.

Usage:
    python restart-sequence.py
    python restart-sequence.py --stop                 (shut down, no restart)
    python restart-sequence.py --cancel               (call off a countdown)
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

HERE = os.path.dirname(os.path.abspath(__file__))
# Ahead of the sibling imports: run as a script Python adds this directory
# itself, but imported from elsewhere it does not, and both need to work.
sys.path.insert(0, HERE)

import rcon      # noqa: E402
import settings  # noqa: E402

# The coordination files live with the server, not with this script.
# start.bat writes server.running beside itself, and watchdog.ps1 reads it
# from there; if this script kept its lock somewhere else the watchdog would
# never see it and would race a restart already in progress.
SERVER_DIR = settings.server_dir()
LOG_PATH = os.path.join(HERE, 'scheduled-restart.log')
START_BAT = settings.get('startBat',
                         default=os.path.join(SERVER_DIR, 'start.bat'))
# watchdog.ps1 restarts the server whenever start.bat's "server.running"
# marker is present but no java process is. For about two seconds after a
# deliberate stop both of those are true, and a watchdog tick landing there
# would launch a second start.bat alongside this one: the port is still free,
# so both pass start.bat's guard, and the loser's java dies unable to bind.
# This lock tells the watchdog a restart is already in hand.
LOCK_PATH = os.path.join(SERVER_DIR, 'restart.lock')
PENDING_PATH = os.path.join(SERVER_DIR, 'restart.pending')
CANCEL_PATH = os.path.join(SERVER_DIR, 'restart.cancel')
GAME_PORT = 25565

# Seconds before the restart, and what to say at that point. The action bar is
# what players actually notice; chat carries the detail. {verb} is 重啟 or 關閉.
SCHEDULE = [
    (300, '伺服器將在 5 分鐘後{verb}（{reason}）', '5 分鐘後{verb}'),
    (180, '伺服器將在 3 分鐘後{verb}', '3 分鐘後{verb}'),
    (60, '伺服器將在 1 分鐘後{verb}，請找安全的地方登出', '1 分鐘後{verb}'),
    (30, '{verb}倒數 30 秒', '{verb}倒數 30'),
    (20, '{verb}倒數 20 秒', '{verb}倒數 20'),
    (10, '{verb}倒數 10 秒', '{verb}倒數 10'),
    (5, '{verb}倒數 5', '5'),
    (4, '{verb}倒數 4', '4'),
    (3, '{verb}倒數 3', '3'),
    (2, '{verb}倒數 2', '2'),
    (1, '{verb}倒數 1', '1'),
]

LEAD_SECONDS = SCHEDULE[0][0]


class Cancelled(Exception):
    pass


def _pid_alive(pid):
    try:
        out = subprocess.run(['tasklist', '/FI', 'PID eq %d' % pid, '/FO', 'CSV', '/NH'],
                             capture_output=True, text=True, timeout=15,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return ('"%d"' % pid) in out.stdout
    except Exception:
        return True     # unsure: better to report a countdown than hide one


def pending():
    """The countdown in progress, or None. A file left by a sequence that
    died is ignored and removed, so a crash cannot block every future stop."""
    try:
        with open(PENDING_PATH, encoding='utf-8') as fh:
            info = json.load(fh)
    except (OSError, ValueError):
        return None
    if not _pid_alive(int(info.get('pid', 0))):
        try:
            os.remove(PENDING_PATH)
        except OSError:
            pass
        return None
    info['seconds_left'] = max(0, int(info.get('deadline', 0) - time.time()))
    return info


def request_cancel():
    with open(CANCEL_PATH, 'w', encoding='utf-8') as fh:
        fh.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + chr(10))


def launch(mode='restart', reason=None, by=''):
    """Start a detached sequence for the consoles and the bot. Returns
    (started, message); refuses while another countdown is running."""
    cur = pending()
    if cur:
        return False, '已經有一個{0}倒數在進行中（剩 {1} 秒）'.format(
            '關閉' if cur.get('mode') == 'stop' else '重啟', cur['seconds_left'])
    pyw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    exe = pyw if os.path.exists(pyw) else sys.executable
    args = [exe, os.path.join(HERE, 'restart-sequence.py')]
    if mode == 'stop':
        args.append('--stop')
    if reason:
        args += ['--reason', reason]
    if by:
        args += ['--by', by]
    flags = (getattr(subprocess, 'CREATE_NO_WINDOW', 0)
             | getattr(subprocess, 'DETACHED_PROCESS', 0)
             | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0))
    subprocess.Popen(args, cwd=HERE, creationflags=flags, close_fds=True)
    return True, '已開始 5 分鐘{0}倒數（沒人在線上會直接{0}）'.format(
        '關閉' if mode == 'stop' else '重啟')


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
        # 26.3 drops the connection when two packets arrive in one read.
        chunks = [rcon.read_packet(self.sock)[2]]
        self.sock.sendall(rcon.pack(sentinel, 2, ''))
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
    # Short naps rather than one long sleep, so a cancel lands within a second.
    while True:
        if os.path.exists(CANCEL_PATH):
            raise Cancelled()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.5, remaining))


def players_online(session):
    # minecraft:list, not list: EssentialsX replaces /list with a translated
    # reply that has no "There are" in it.
    ok, out = session.run('minecraft:list')
    if not ok:
        return None
    try:
        count = int(out.split('There are', 1)[1].split()[0])
    except (IndexError, ValueError):
        return None
    # FakePlayerPlugin bots are in that count but nobody needs a warning.
    if count:
        ok, bots = session.run('fpp list')
        if ok:
            people = set(rcon.list_names(out)) - set(rcon.bot_names(bots))
            count = len(people)
    return count


def stop_server(session):
    session.run('save-all')
    ok, detail = session.run('stop')
    log('stop issued: {0}'.format(detail.replace(chr(10), ' | ')))
    session.close()

    # Ten minutes, not two. A shutdown save scales with how much of the world
    # has been touched: the same server that stopped in 5 seconds one day took
    # 8m37s the next, after a few days of heavy building. Timing out here does
    # not restart the server, so a cap that is merely usually enough leaves the
    # server down on exactly the days it was busiest.
    for _ in range(200):
        time.sleep(3)
        if not port_open(GAME_PORT):
            log('Server stopped')
            return True
    return False


def start_server():
    # stop_server() returns once the game port closes, but java may still be
    # saving the world then. Wait for that process to go rather than taking it
    # for a server someone else started, which would leave the server down
    # after a slow save. The port coming back does mean someone else started it.
    deadline = time.monotonic() + 600
    while server_process_running():
        if port_open(GAME_PORT):
            log('A server process is already running - not starting a second one',
                'WARN')
            return True
        if time.monotonic() > deadline:
            log('The old server process is still there after 10 minutes - '
                'not starting a second one', 'ERROR')
            return False
        time.sleep(3)
    # The old start.bat stops playit once its java is gone. Let it finish, or
    # it can stop the tunnel the new start.bat has just started.
    time.sleep(10)

    # start.bat brings the playit tunnel and the map sync back up as well.
    subprocess.Popen(
        settings.server_launch_command(START_BAT),
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
    parser.add_argument('--stop', action='store_true',
                        help='shut down after the countdown, do not restart')
    parser.add_argument('--cancel', action='store_true',
                        help='call off a countdown that is running')
    parser.add_argument('--by', default='', help='who asked, for the log')
    parser.add_argument('--reason', default=None)
    args = parser.parse_args()

    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    if args.cancel:
        if not pending():
            print('沒有進行中的倒數')
            return 0
        request_cancel()
        print('已要求取消倒數')
        return 0

    if not port_open(GAME_PORT):
        log('Server is not running - nothing to restart')
        return 0
    if pending():
        log('Another countdown is already running - not starting a second', 'WARN')
        return 1

    verb = '關閉' if args.stop else '重啟'
    reason = args.reason or ('管理員關閉伺服器' if args.stop else '定期重啟以釋放記憶體')
    compress = max(1, args.compress)

    # A cancel left over from an earlier run must not kill this one.
    try:
        os.remove(CANCEL_PATH)
    except OSError:
        pass

    session = Session()
    online = players_online(session)
    # Nobody to warn: act now. Unknown (RCON hiccup) counts as someone there.
    lead = 0 if online == 0 else LEAD_SECONDS
    log('{0} sequence started by {1} (online: {2}, dry run: {3}, compress: {4}x)'.format(
        'Stop' if args.stop else 'Restart', args.by or '?', online, args.dry_run, compress))

    with open(PENDING_PATH, 'w', encoding='utf-8') as fh:
        json.dump({'mode': 'stop' if args.stop else 'restart', 'pid': os.getpid(),
                   'deadline': time.time() + lead / compress, 'by': args.by,
                   'reason': reason}, fh, ensure_ascii=False)

    # Absolute deadlines from a single origin, so a slow command eats into its
    # own slot instead of pushing every later announcement back.
    origin = time.monotonic()

    try:
        if lead:
            for before, chat, action_bar in SCHEDULE:
                wait_until(origin + (LEAD_SECONDS - before) / compress)
                announce(session, chat.format(reason=reason, verb=verb),
                         action_bar.format(verb=verb))
            wait_until(origin + LEAD_SECONDS / compress)
        else:
            log('Nobody online - skipping the countdown')

        if args.dry_run:
            announce(session, '（演練）這裡就會{0}，實際上不會'.format(verb), None)
            log('Dry run: stopping here')
            return 0

        if args.stop:
            announce(session, '伺服器關閉中', '關閉中')
        else:
            announce(session, '伺服器重啟中，約 40 秒後回來', '重啟中')

        take_lock()
        if not stop_server(session):
            log('Server did not stop within 10 minutes - '
                'not starting a second one', 'ERROR')
            return 1

        if args.stop:
            return 0
        if not start_server():
            log('Server did not come back within 3 minutes', 'ERROR')
            return 1
        return 0
    except Cancelled:
        announce(session, '{0}已取消，請繼續遊戲'.format(verb), '{0}已取消'.format(verb))
        log('Countdown cancelled')
        return 0
    finally:
        session.close()
        release_lock()
        for path in (PENDING_PATH, CANCEL_PATH):
            try:
                os.remove(path)
            except OSError:
                pass


if __name__ == '__main__':
    sys.exit(main())
