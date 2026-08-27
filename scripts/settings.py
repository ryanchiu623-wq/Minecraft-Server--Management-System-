#!/usr/bin/env python3
"""Shared configuration for every tool in this toolkit.

One config.json for the whole project, so an install is "fill in one file"
rather than editing constants scattered through eight scripts.

Lookup order:
  1. $MC_TOOLKIT_CONFIG, if set
  2. config.json beside this file
  3. config.json in the parent directory (the usual layout: scripts/ under
     the repository root)

Secrets are never stored here. Anything sensitive - the Discord bot token,
the Cloudflare API token - is referenced by a path to a file holding it, so
config.json itself is safe to keep next to the code (though .gitignore
excludes it anyway, since it still carries your addresses).
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULTS = {
    "serverDir": "",
    "backupDir": "",
    "startBat": "",
    "keepBackups": 7,
    "java": {"host": "", "port": 25565, "localPort": 25565},
    "bedrock": {"host": "", "tunnelPort": 19132, "localPort": 19132},
    "mapUrl": "",
    "webConsole": {"host": "0.0.0.0", "port": 8099},
    "discord": {
        "tokenFile": "",
        "authorizedUserIds": [],
        "rconUserIds": [],
        "logChannelId": "",
    },
    "cloudflare": {
        "projectName": "",
        "accountId": "",
        "tokenFile": "",
        "webDir": "",
    },
}


def _merge(base, override):
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def config_path():
    env = os.environ.get("MC_TOOLKIT_CONFIG")
    if env:
        return env
    for candidate in (os.path.join(HERE, "config.json"),
                      os.path.join(os.path.dirname(HERE), "config.json")):
        if os.path.exists(candidate):
            return candidate
    return os.path.join(os.path.dirname(HERE), "config.json")


def load():
    path = config_path()
    try:
        with open(path, encoding="utf-8") as fh:
            user = json.load(fh)
    except FileNotFoundError:
        raise SystemExit(
            "找不到設定檔：%s\n"
            "請複製 config.example.json 為 config.json 再填入你的資訊。" % path)
    except ValueError as exc:
        raise SystemExit("設定檔不是有效的 JSON：%s\n%s" % (path, exc))
    return _merge(DEFAULTS, user)


CONFIG = load()


def require(*keys):
    """Fetch a nested value, failing loudly rather than running on a blank.

    An empty host silently turns every probe into "offline", which is a much
    worse failure than refusing to start.
    """
    node = CONFIG
    for key in keys:
        node = node.get(key, {}) if isinstance(node, dict) else {}
    if node in ("", None, [], {}):
        raise SystemExit("設定檔缺少必要欄位：%s" % ".".join(keys))
    return node


def get(*keys, default=None):
    node = CONFIG
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node if node not in ("", None) else default


def server_dir():
    return get("serverDir", default=os.path.dirname(HERE))
