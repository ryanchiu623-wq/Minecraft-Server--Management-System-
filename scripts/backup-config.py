#!/usr/bin/env python3
"""Back up everything a restore needs besides the world itself.

backup-world.ps1 only zips the world folder. Restoring onto a fresh disk from
that alone would lose the whitelist, ops and server.properties, every plugin's
data (LuckPerms groups, EssentialsX homes, WorldGuard regions, the Floodgate
key that keeps Bedrock players' identities, DiscordSRV account links,
StellarProtect history, the bots), the plugin jars at their exact versions,
the toolkit's own scripts - which live nowhere else - and the tunnels'
credentials. This zips all of that into config-<stamp>.zip next to the world
backups. It is small (about 100 MB); the BlueMap tiles and Flashback replays
are left out because they can be rebuilt or are only kept for 36 hours anyway.

Databases a running server keeps open are copied safely: LuckPerms through
"lp export" (its H2 file is locked), SQLite files through SQLite's online
backup. The zip holds secrets (Discord bot token, RCON password, tunnel
credentials) - keep any copy of it private.

Usage:  python backup-config.py [--dest DIR] [--keep N]
Called by windows/backup-world.ps1 after the world backup.
"""
import argparse
import datetime
import glob
import os
import sqlite3
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rcon      # noqa: E402
import settings  # noqa: E402

SERVER_DIR = settings.server_dir()
TOOLKIT_DIR = os.path.dirname(HERE)
LP_EXPORT = 'toolkit-backup'

# Files at the top of the server folder that only describe the moment.
SKIP_SERVER_FILES = {'server.running', 'restart.lock', 'restart.pending', 'restart.cancel'}
# Relative to the server folder. Rebuildable, re-downloaded, or short-lived.
SKIP_SERVER_DIRS = {
    os.path.join('plugins', 'LuckPerms', 'libs'),
    os.path.join('plugins', 'SimplyFlashback', 'replays'),
    os.path.join('plugins', 'SimplyFlashback', 'clips'),
    os.path.join('plugins', 'update'),
}
# H2 keeps its file locked; "lp export" stands in for it.
SKIP_LOCKED = ('.mv.db', '.trace.db')
SQLITE = ('.db', '.sqlite', '.sqlite3')

README = """這是 Minecraft 伺服器的設定與外掛資料備份（世界在同一資料夾的 world-*.zip）。

server\\     -> C:\\mc-paper 的設定檔、paper.jar、config\\、plugins\\（含外掛 jar 與資料）
toolkit\\    -> C:\\mc-toolkit（管理腳本、設定、手冊）
cloudflared\\ -> %USERPROFILE%\\.cloudflared（地圖與控制台的 Cloudflare 隧道）
playit\\     -> C:\\ProgramData\\playit_gg\\playit.toml（Java 版的 playit 隧道）

還原：先關伺服器、停看門狗，把 server\\ 的內容放回 C:\\mc-paper，toolkit\\ 放回 C:\\mc-toolkit，
再把 world-*.zip 解壓成 C:\\mc-paper\\world。LuckPerms 的權限要另外匯入：
伺服器開好後在主控台下 lp import toolkit-backup（檔案在 plugins\\LuckPerms\\toolkit-backup.json.gz）。

這個壓縮檔含有密碼與權杖，不要分享給別人。
"""


def lp_export():
    """Ask LuckPerms for a fresh export; True once the file is written."""
    path = os.path.join(SERVER_DIR, 'plugins', 'LuckPerms', LP_EXPORT + '.json.gz')
    try:
        os.remove(path)   # LuckPerms will not overwrite an existing export
    except OSError:
        pass
    try:
        ok, _ = rcon.execute_each(['lp export ' + LP_EXPORT])
    except Exception:
        ok = False
    if not ok:
        return False
    # The export runs asynchronously; wait until the file stops growing.
    last = -1
    for _ in range(30):
        time.sleep(1)
        size = os.path.getsize(path) if os.path.exists(path) else -1
        if size > 0 and size == last:
            return True
        last = size
    return os.path.exists(path)


def sqlite_copy(path):
    """A consistent copy of a SQLite file another process has open."""
    fd, tmp = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    src = sqlite3.connect('file:%s?mode=ro' % path, uri=True, timeout=10)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return tmp


def server_files():
    for name in sorted(os.listdir(SERVER_DIR)):
        full = os.path.join(SERVER_DIR, name)
        if os.path.isfile(full) and name not in SKIP_SERVER_FILES:
            yield full, os.path.join('server', name)
    for top in ('config', 'plugins'):
        for root, dirs, files in os.walk(os.path.join(SERVER_DIR, top)):
            rel_root = os.path.relpath(root, SERVER_DIR)
            dirs[:] = [d for d in dirs if os.path.join(rel_root, d) not in SKIP_SERVER_DIRS]
            for f in files:
                yield os.path.join(root, f), os.path.join('server', rel_root, f)


def toolkit_files():
    for root, dirs, files in os.walk(TOOLKIT_DIR):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        for f in files:
            if f.endswith('.log'):
                continue
            full = os.path.join(root, f)
            yield full, os.path.join('toolkit', os.path.relpath(full, TOOLKIT_DIR))


def tunnel_files():
    cf = os.path.join(os.path.expanduser('~'), '.cloudflared')
    if os.path.isdir(cf):
        for f in os.listdir(cf):
            full = os.path.join(cf, f)
            if os.path.isfile(full) and not f.endswith('.log'):
                yield full, os.path.join('cloudflared', f)
    playit = os.path.join(os.environ.get('ProgramData', r'C:\ProgramData'), 'playit_gg', 'playit.toml')
    if os.path.isfile(playit):
        yield playit, os.path.join('playit', 'playit.toml')


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser()
    parser.add_argument('--dest', default=settings.get('backupDir', default=r'E:\mc-backup'))
    parser.add_argument('--keep', type=int, default=int(settings.get('keepBackups', default=7)))
    args = parser.parse_args()

    exported = lp_export()
    print('LuckPerms export: %s' % ('written' if exported else
                                    'skipped (server not running) - its database file is copied instead'))

    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    os.makedirs(args.dest, exist_ok=True)
    final = os.path.join(args.dest, 'config-%s.zip' % stamp)
    part = final + '.part'
    count, skipped = 0, []
    with zipfile.ZipFile(part, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr('README.txt', README)
        for full, arc in list(server_files()) + list(toolkit_files()) + list(tunnel_files()):
            lower = full.lower()
            try:
                if lower.endswith(SKIP_LOCKED) and exported:
                    continue
                if lower.endswith(SQLITE):
                    try:
                        tmp = sqlite_copy(full)
                    except sqlite3.Error:
                        tmp = None   # not a SQLite file after all - copy it as is
                    if tmp:
                        try:
                            zf.write(tmp, arc)
                        finally:
                            os.remove(tmp)
                        count += 1
                        continue
                zf.write(full, arc)
                count += 1
            except (OSError, sqlite3.Error) as exc:
                skipped.append('%s (%s)' % (arc, exc.__class__.__name__))
    os.replace(part, final)
    print('Wrote %s (%d files, %.1f MB)' % (final, count, os.path.getsize(final) / 1048576))
    for s in skipped:
        print('Skipped %s' % s)

    old = sorted(glob.glob(os.path.join(args.dest, 'config-*.zip')), key=os.path.getmtime)
    for path in old[:-args.keep] if len(old) > args.keep else []:
        os.remove(path)
        print('Removed old %s' % os.path.basename(path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
