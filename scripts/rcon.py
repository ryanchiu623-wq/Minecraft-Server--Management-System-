#!/usr/bin/env python3
"""Minimal Source-RCON client for the local Minecraft server.

Reads host/port/password straight out of server.properties so the
credential never has to be passed around on the command line.

Usage:  python rcon.py "<command>" ["<command>" ...]
"""
import socket, struct, sys, os, re

HERE = os.path.dirname(os.path.abspath(__file__))

# Server replies contain characters the Windows cp950 console cannot encode.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def _server_properties_path():
    """Locate server.properties.

    The scripts live in scripts/ while server.properties sits in the server
    directory, so "next to this file" is only right for a standalone copy.
    Falls back to that when the toolkit config is unavailable, which keeps
    rcon.py usable on its own.
    """
    try:
        import sys
        sys.path.insert(0, HERE)
        import settings
        return os.path.join(settings.server_dir(), 'server.properties')
    except Exception:
        return os.path.join(HERE, 'server.properties')


def load_props(path=None):
    path = path or _server_properties_path()
    props = {}
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                props[k.strip()] = v.strip()
    return props


def strip_colors(text):
    """Remove Minecraft section-sign colour codes, including hex (§x§R§R...)."""
    return re.sub(r'§[0-9a-fk-orx]', '', text, flags=re.IGNORECASE)


def pack(req_id, req_type, body):
    payload = struct.pack('<ii', req_id, req_type) + body.encode('utf-8') + b'\x00\x00'
    return struct.pack('<i', len(payload)) + payload


def read_exact(sock, n):
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise IOError('connection closed by server')
        buf += chunk
    return buf


def read_packet(sock):
    (length,) = struct.unpack('<i', read_exact(sock, 4))
    data = read_exact(sock, length)
    req_id, req_type = struct.unpack('<ii', data[:8])
    return req_id, req_type, data[8:-2].decode('utf-8', 'replace')


def execute_each(commands, props=None):
    """Run commands and return (ok, [reply, ...]) - one reply per command.

    Callers that query a list of values need the replies kept apart. Joining
    them cannot be undone: an error reply is itself two lines ("Incorrect
    argument for command" plus the caret line), so splitting a joined string
    pairs every later command with the wrong answer - quietly, and with
    plausible-looking results.
    """
    props = props or load_props()
    host = props.get('server-ip') or '127.0.0.1'
    port = int(props.get('rcon.port', 25575))
    password = props.get('rcon.password', '')

    if props.get('enable-rcon', 'false') != 'true':
        return False, ['enable-rcon is not true in server.properties']
    if not password:
        return False, ['rcon.password is empty']

    out = []
    try:
        with socket.create_connection((host, port), timeout=8) as sock:
            sock.sendall(pack(1, 3, password))
            req_id, _, _ = read_packet(sock)
            if req_id == -1:
                return False, ['RCON 認證失敗（密碼不符）']

            SENTINEL = 9999
            for i, cmd in enumerate(commands, start=2):
                sock.sendall(pack(i, 2, cmd))
                sock.sendall(pack(SENTINEL, 2, ''))
                chunks = []
                while True:
                    rid, _, body = read_packet(sock)
                    if rid == SENTINEL:
                        break
                    chunks.append(body)
                out.append(strip_colors(''.join(chunks)).strip())
    except Exception as exc:
        return False, ['{0}: {1}'.format(type(exc).__name__, exc)]

    return True, out


def execute(commands, props=None):
    """Run commands and return (ok, text). Importable so the desktop console
    can call this in-process - once frozen into an .exe, sys.executable is
    the exe itself, so shelling out to "python rcon.py" no longer works."""
    ok, replies = execute_each(commands, props)
    if not ok:
        return False, replies[0] if replies else ''
    return True, chr(10).join(replies)


def main():
    if len(sys.argv) < 2:
        print('usage: python rcon.py "<command>" [...]')
        return 2

    props = load_props()
    host = props.get('server-ip') or '127.0.0.1'
    port = int(props.get('rcon.port', 25575))
    password = props.get('rcon.password', '')

    if props.get('enable-rcon', 'false') != 'true':
        print('enable-rcon is not true in server.properties')
        return 1
    if not password:
        print('rcon.password is empty')
        return 1

    with socket.create_connection((host, port), timeout=8) as sock:
        sock.sendall(pack(1, 3, password))          # 3 = auth
        req_id, _, _ = read_packet(sock)
        if req_id == -1:
            print('RCON 認證失敗（密碼不符）')
            return 1

        # Long replies are split across several packets. Send a sentinel after
        # each command and collect packets until the sentinel's reply comes
        # back - everything before it belongs to the command.
        SENTINEL = 9999
        for i, cmd in enumerate(sys.argv[1:], start=2):
            sock.sendall(pack(i, 2, cmd))           # 2 = command
            sock.sendall(pack(SENTINEL, 2, ''))
            chunks = []
            while True:
                req_id, _, body = read_packet(sock)
                if req_id == SENTINEL:
                    break
                chunks.append(body)
            reply = strip_colors(''.join(chunks)).strip()
            print(f'> {cmd}')
            print(reply if reply else '(伺服器沒有回傳文字)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
