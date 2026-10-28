#!/usr/bin/env python3
"""Keep a SimplyFlashback recording running for every player who is online.

SimplyFlashback only records on request (/sf record start <player>). The
scheduled task "MC Toolkit Flashback Recorder" runs this every minute: anyone
online without a recording gets one. A recording ends when the player leaves or
after recording.max-duration-seconds (an hour on this server), and the next run
starts the following piece, so at most a minute is missed.

Old replays are removed by windows/flashback-cleanup.ps1.

Each run also copies finished replays into the Flashback mod's replay folder
(flashback.clientReplayDir in config.json). The mod only lists .zip files, and
SimplyFlashback saves .flashback - the same zip under another name - so the
copies are renamed. Copies older than flashback.keepHours go again, like the
originals; a copy the viewer renamed to keep is left alone.

Usage:  pythonw flashback-record.py
"""
import json, os, re, shutil, sys, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rcon, settings

LOG = os.path.join(HERE, "flashback-record.log")
SYNCED = os.path.join(HERE, "flashback-synced.json")


def log(msg, level="INFO"):
    line = "%s [%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), level, msg)
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 1024 * 1024:
            with open(LOG, encoding="utf-8", errors="replace") as fh:
                tail = fh.readlines()[-200:]
            with open(LOG, "w", encoding="utf-8") as fh:
                fh.writelines(tail)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass


def online_players(list_reply):
    # "There are 2 of a max of 20 players online: ryanchiu623, .Ryanchiu623"
    _, _, names = list_reply.partition(":")
    return [n.strip() for n in names.split(",") if re.fullmatch(r"[A-Za-z0-9_.]{1,17}", n.strip())]


def finished_replays(sf_dir):
    """Saved replays and clips. clips/tmp holds live clip buffers - skip it."""
    for tree in ("replays", "clips"):
        root = os.path.join(sf_dir, tree)
        for dirpath, dirnames, files in os.walk(root):
            if dirpath == root:
                dirnames[:] = [d for d in dirnames if d != "tmp"]
            for f in files:
                if f.endswith(".flashback"):
                    yield os.path.join(dirpath, f)


def sync_to_viewer():
    target = settings.get("flashback", "clientReplayDir", default="")
    if not target or not os.path.isdir(target):
        return
    keep = float(settings.get("flashback", "keepHours", default=36)) * 3600
    sf_dir = os.path.join(settings.server_dir(), "plugins", "SimplyFlashback")
    try:
        with open(SYNCED, encoding="utf-8") as fh:
            synced = json.load(fh)
    except (OSError, ValueError):
        synced = {}
    now = time.time()
    changed = False

    for src in finished_replays(sf_dir):
        name = os.path.basename(src)[:-len(".flashback")] + ".zip"
        st = os.stat(src)
        # Under a minute old may still be being written; past keepHours the
        # cleanup is about to take the original anyway.
        if name in synced or not 60 < now - st.st_mtime < keep:
            continue
        try:
            with zipfile.ZipFile(src) as z:
                if "metadata.json" not in z.namelist():
                    continue
        except (OSError, zipfile.BadZipFile):
            continue
        dest = os.path.join(target, name)
        # Copy under a name Flashback ignores, then rename: the replay list
        # never shows a half-copied file.
        shutil.copy2(src, dest + ".part")
        os.replace(dest + ".part", dest)
        synced[name] = {"size": st.st_size, "source": src}
        changed = True
        log("copied %s to the Flashback replay folder" % name)

    for name, info in list(synced.items()):
        dest = os.path.join(target, name)
        if os.path.exists(dest):
            # copy2 kept the recording's own time, so this ages like the original.
            if os.path.getsize(dest) == info["size"] and now - os.path.getmtime(dest) > keep:
                os.remove(dest)
                log("removed %s from the Flashback replay folder (older than %d h)"
                    % (name, keep / 3600))
                changed = True
        # Forget a copy once both it and its original are gone; while the
        # original is still there the entry stops a deleted copy coming back.
        if not os.path.exists(dest) and not os.path.exists(info["source"]):
            del synced[name]
            changed = True

    if changed:
        with open(SYNCED + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(synced, fh, ensure_ascii=False, indent=1)
        os.replace(SYNCED + ".tmp", SYNCED)


def main():
    try:
        sync_to_viewer()
    except Exception as exc:      # never let the copy stop the recording
        log("copying replays to Flashback failed: %s" % exc, "WARN")
    if not settings.get("flashback", "autoRecord", default=True):
        return 0
    # minecraft:list: EssentialsX's /list replies in another format and language.
    # fpp list: FakePlayerPlugin bots are listed as players but are not recorded.
    ok, replies = rcon.execute_each(["minecraft:list", "fpp list"])
    if not ok:
        return 0        # server is down or starting: nothing to record
    bots = set(rcon.bot_names(replies[1]))
    players = [p for p in online_players(replies[0]) if p not in bots]
    if not players:
        return 0
    ok, replies = rcon.execute_each(["sf record start %s" % p for p in players])
    if not ok:
        log("could not start recordings: %s" % replies[0], "WARN")
        return 1
    for player, reply in zip(players, replies):
        if "already being recorded" in reply or "still writing" in reply:
            continue
        log("%s -> %s" % (player, reply or "(no reply)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
