#!/usr/bin/env python3
"""Plugin catalogue and downloader for the installer.

Two sources, because no single one covers what this toolkit needs:

  Modrinth   has a clean public API and carries most of them.
  GeyserMC   is the only place with a Paper build of Floodgate, and Floodgate
             is exactly the piece people miss - without it Bedrock players are
             still asked for a Java account, which defeats the point.

Anything not reachable from an API is listed anyway, with a link, so an
install ends knowing what it still has to fetch by hand rather than finding
out when a feature silently does nothing.
"""

import json
import os
import urllib.parse
import urllib.request

UA = {"User-Agent": "mc-toolkit-installer/1.0 (github.com/ryanchiu623-wq)"}
MODRINTH = "https://api.modrinth.com/v2"
GEYSER = "https://download.geysermc.org/v2/projects"


class Plugin:
    def __init__(self, key, name, source, slug, default, note=""):
        self.key = key
        self.name = name
        self.source = source        # modrinth | geyser | manual
        self.slug = slug
        self.default = default
        self.note = note


CATALOGUE = [
    Plugin("geyser", "Geyser", "geyser", "geyser", True,
           "讓基岩版玩家連得進來"),
    Plugin("floodgate", "Floodgate", "geyser", "floodgate", True,
           "基岩版玩家免 Java 帳號"),
    Plugin("bluemap", "BlueMap", "modrinth", "bluemap", True,
           "3D 網頁地圖"),
    Plugin("deluxemenus", "DeluxeMenus", "modrinth", "deluxemenus", True,
           "PanelKey 的 /menu 靠它顯示"),
    Plugin("placeholderapi", "PlaceholderAPI", "modrinth", "placeholderapi",
           True, "指定給予對象需要"),
    Plugin("luckperms", "LuckPerms", "modrinth", "luckperms", False,
           "權限管理"),
    Plugin("worldedit", "WorldEdit", "modrinth", "worldedit", False,
           "大範圍編輯"),
    Plugin("worldguard", "WorldGuard", "modrinth", "worldguard", False,
           "區域保護（需要 WorldEdit）"),
    Plugin("discordsrv", "DiscordSRV", "modrinth", "discordsrv", False,
           "遊戲與 Discord 聊天互通"),
]

# Not fetchable: their own sites, or paid platforms with bot protection.
MANUAL = [
    ("Citizens", "https://ci.citizensnpcs.co/job/Citizens2/"),
    ("Sentinel", "https://ci.citizensnpcs.co/job/Sentinel/"),
    ("InventoryStacks", "https://www.spigotmc.org/resources/inventorystacks.109864/"),
]


def _get(url):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=30).read())


def resolve(plugin):
    """Return (download_url, filename, version_label)."""
    if plugin.source == "modrinth":
        loaders = urllib.parse.quote('["paper"]')
        versions = _get("%s/project/%s/version?loaders=%s"
                        % (MODRINTH, plugin.slug, loaders))
        if not versions:
            raise RuntimeError("Modrinth 上沒有 paper 版本")
        latest = versions[0]
        entry = latest["files"][0]
        # A multi-file release marks the one to actually install.
        for f in latest["files"]:
            if f.get("primary"):
                entry = f
                break
        return entry["url"], entry["filename"], latest.get("version_number", "")

    if plugin.source == "geyser":
        project = _get("%s/%s" % (GEYSER, plugin.slug))
        version = project["versions"][-1]
        build = _get("%s/%s/versions/%s/builds/latest"
                     % (GEYSER, plugin.slug, version))
        downloads = build.get("downloads", {})
        key = "spigot" if "spigot" in downloads else next(iter(downloads))
        entry = downloads[key]
        url = ("%s/%s/versions/%s/builds/%s/downloads/%s"
               % (GEYSER, plugin.slug, version, build["build"], key))
        return url, entry["name"], "%s build %s" % (version, build["build"])

    raise RuntimeError("這個外掛沒有自動下載來源")


def download(plugin, plugins_dir, progress=None):
    """Fetch one plugin into plugins_dir; returns the filename written."""
    url, filename, label = resolve(plugin)
    os.makedirs(plugins_dir, exist_ok=True)

    # Replace any earlier build of the same plugin: two jars of one plugin
    # load unpredictably and the server gives no warning.
    stem = filename.split("-")[0].lower()
    for existing in os.listdir(plugins_dir):
        if (existing.lower().startswith(stem) and existing.endswith(".jar")
                and existing != filename):
            try:
                os.remove(os.path.join(plugins_dir, existing))
            except OSError:
                pass

    target = os.path.join(plugins_dir, filename)
    with urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=180) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        got = 0
        with open(target, "wb") as fh:
            while True:
                chunk = resp.read(262144)
                if not chunk:
                    break
                fh.write(chunk)
                got += len(chunk)
                if progress and total:
                    progress(got / total)
    return filename, label
