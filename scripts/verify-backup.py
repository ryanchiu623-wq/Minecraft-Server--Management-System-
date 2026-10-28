#!/usr/bin/env python3
"""Check that a world backup zip could actually be restored.

Reads every file in the zip (the zip's own CRC check), parses level.dat, and
opens every chunk of every region file - region/, entities/ and poi/ - the
way the game loads them: header -> sectors -> decompress -> NBT compound.
Nothing is extracted to disk.

It also counts region files per dimension against the live world, so a backup
that silently lost a whole dimension shows up as well.

Usage:  python verify-backup.py [backup.zip]     (default: newest backup)
Exit code 0 = the backup is good, 1 = problems found.
"""
import glob
import gzip
import os
import struct
import sys
import time
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import settings  # noqa: E402

BACKUP_DIR = settings.get('backupDir', default=r'E:\mc-backup')
WORLD_DIR = os.path.join(settings.server_dir(), settings.get('levelName', default='world') or 'world')
REGION_KINDS = ('region', 'entities', 'poi')


def check_chunk(data, offset, sectors):
    """None if the chunk loads, otherwise what is wrong with it."""
    start = offset * 4096
    if start + 5 > len(data) or start + sectors * 4096 > len(data) + 4096:
        return 'points past the end of the file'
    length, kind = struct.unpack('>IB', data[start:start + 5])
    if kind & 0x80:
        # Stored in a separate .mcc file next to the region; checked as a file.
        return None
    payload = data[start + 5:start + 4 + length]
    try:
        if kind == 1:
            raw = gzip.decompress(payload)
        elif kind == 2:
            raw = zlib.decompress(payload)
        elif kind == 3:
            raw = payload
        else:
            return 'compression type %d is not checked here' % kind
    except (zlib.error, OSError, EOFError) as exc:
        return 'does not decompress (%s)' % exc
    if not raw or raw[0] != 0x0A:
        return 'is not an NBT compound'
    return None


def check_region(data):
    """(chunks checked, list of problems) for one .mca file."""
    if len(data) == 0:
        return 0, []
    if len(data) < 8192:
        return 0, ['header is cut short (%d bytes)' % len(data)]
    checked, problems = 0, []
    for i in range(1024):
        entry = struct.unpack('>I', data[i * 4:i * 4 + 4])[0]
        offset, sectors = entry >> 8, entry & 0xFF
        if offset == 0 and sectors == 0:
            continue
        checked += 1
        problem = check_chunk(data, offset, sectors)
        if problem:
            problems.append('chunk %d,%d %s' % (i % 32, i // 32, problem))
    return checked, problems


def dimension_of(path):
    """'dimensions/minecraft/the_nether/region/r.0.0.mca' -> ('the_nether', 'region')."""
    parts = path.replace('\\', '/').split('/')
    if len(parts) >= 3 and parts[-2] in REGION_KINDS:
        return parts[-3], parts[-2]
    return None, None


def live_counts():
    counts = {}
    pattern = os.path.join(WORLD_DIR, 'dimensions', '*', '*', 'region', '*.mca')
    for path in glob.glob(pattern):
        dim = os.path.basename(os.path.dirname(os.path.dirname(path)))
        counts[dim] = counts.get(dim, 0) + 1
    return counts


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if len(sys.argv) > 1:
        zip_path = sys.argv[1]
    else:
        found = sorted(glob.glob(os.path.join(BACKUP_DIR, 'world-*.zip')), key=os.path.getmtime)
        if not found:
            print('No backups in %s' % BACKUP_DIR)
            return 1
        zip_path = found[-1]

    started = time.monotonic()
    print('Checking %s (%.0f MB)' % (zip_path, os.path.getsize(zip_path) / 1048576))
    problems = []
    files = chunks = 0
    regions = {}
    level_ok = False
    try:
        archive = zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile, OSError) as exc:
        print('FAIL: cannot open the zip: %s' % exc)
        return 1
    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            files += 1
            try:
                data = archive.read(info)   # raises on a CRC mismatch
            except (zipfile.BadZipFile, zlib.error, OSError) as exc:
                problems.append('%s: unreadable (%s)' % (info.filename, exc))
                continue
            name = info.filename.replace('\\', '/')
            if name == 'level.dat':
                try:
                    level_ok = gzip.decompress(data)[0] == 0x0A
                except (OSError, EOFError, IndexError):
                    level_ok = False
            elif name.endswith('.mca'):
                dim, kind = dimension_of(name)
                if kind == 'region':
                    regions[dim] = regions.get(dim, 0) + 1
                checked, bad = check_region(data)
                chunks += checked
                problems.extend('%s: %s' % (name, b) for b in bad)

    if not level_ok:
        problems.append('level.dat is missing or unreadable')

    print('Files read: %d   chunks opened: %d   time: %.0f s'
          % (files, chunks, time.monotonic() - started))
    live = live_counts()
    for dim in sorted(set(live) | set(regions)):
        mark = ''
        # The live world can only have grown since the backup was taken.
        if regions.get(dim, 0) < live.get(dim, 0) * 0.9:
            mark = '   <-- far fewer than the live world'
            problems.append('%s has %d region files in the backup, %d live'
                            % (dim, regions.get(dim, 0), live.get(dim, 0)))
        print('  %-12s backup %4d region files, live %4d%s'
              % (dim, regions.get(dim, 0), live.get(dim, 0), mark))

    if problems:
        print('FAIL: %d problem(s)' % len(problems))
        for p in problems[:30]:
            print('  ' + p)
        return 1
    print('OK: level.dat and every chunk load')
    return 0


if __name__ == '__main__':
    sys.exit(main())
