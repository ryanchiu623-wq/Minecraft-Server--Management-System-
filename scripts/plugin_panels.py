#!/usr/bin/env python3
"""Per-plugin panels for the web console.

Each plugin gets a small catalogue entry: what it is, the buttons it offers,
and the form fields those buttons take. The page renders forms from that
description, so adding a button is a matter of adding a line here.

Two things shape how a plugin is driven:

  Arguments are validated against a fixed pattern per field type before they
  are put into a command. RCON runs everything with console rights, so a
  player name that smuggled in a space or a second command would be a hole.

  LuckPerms, WorldGuard, spark and Floodgate answer commands asynchronously.
  Paper's RCON only returns what a command printed while it was running, so
  their replies never arrive. For those plugins the command is sent and the
  result is read back from the files the plugin writes: a LuckPerms export,
  regions.yml, spark's activity.json, whitelist.json. Every one of them was
  checked against the live server - none of the RCON replies came back.

Item names and icons come from the Minecraft client jar BlueMap already
downloaded, and Traditional Chinese names from Mojang's asset server, cached
on first use.
"""

import gzip
import importlib.util
import json
import os
import re
import sqlite3
import threading
import time
import urllib.request
import zipfile

import settings

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = settings.server_dir()
PLUGINS_DIR = os.path.join(SERVER_DIR, "plugins")
CACHE_DIR = os.path.join(HERE, "cache")
UA = {"User-Agent": "mc-toolkit-console/1.0 (github.com/ryanchiu623-wq)"}

rcon = None     # set by setup(); the web console already has rcon.py loaded


def setup(rcon_module):
    global rcon
    rcon = rcon_module
    threading.Thread(target=_load_zh_names, daemon=True).start()


def _load_sibling(name, filename):
    spec = importlib.util.spec_from_file_location(name,
                                                  os.path.join(HERE, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


nbt = _load_sibling("nbt", "litematic2structure.py")


# ------------------------------------------------------------- field checks
PATTERNS = {
    # Floodgate puts a "." in front of Bedrock names.
    "player": r"[A-Za-z0-9_.]{1,17}",
    "group": r"[a-z0-9_\-]{1,36}",
    "node": r"[A-Za-z0-9_.\-*]{1,100}",
    "region": r"[A-Za-z0-9_\-]{1,60}",
    "flag": r"[a-z\-]{1,40}",
    "item": r"(minecraft:)?[a-z0-9_]{1,60}",
}


class BadInput(ValueError):
    pass


def F(name, label, kind, **extra):
    d = {"name": name, "label": label, "kind": kind}
    d.update(extra)
    return d


def A(id_, label, fields, cmds, mode="sync", danger=False, note="",
      settle=1.5):
    """mode: sync returns the RCON reply; async sends and lets the panel
    re-read the plugin's files after `settle` seconds."""
    return {"id": id_, "label": label, "fields": fields, "cmds": cmds,
            "mode": mode, "danger": danger, "note": note, "settle": settle}


def _clean(field, raw):
    value = str(raw if raw is not None else "").strip()
    kind = field["kind"]
    if kind in PATTERNS:
        if not re.fullmatch(PATTERNS[kind], value):
            raise BadInput("「%s」格式不對：%s" % (field["label"], value or "（空白）"))
        return value
    if kind == "choice":
        allowed = [o if isinstance(o, str) else o[0]
                   for o in _options(field)]
        if value not in allowed:
            raise BadInput("「%s」不是可選的值：%s" % (field["label"], value))
        return value
    if kind == "int":
        try:
            n = int(value)
        except ValueError:
            raise BadInput("「%s」要是整數" % field["label"])
        lo, hi = field.get("min", -2**31), field.get("max", 2**31 - 1)
        if not lo <= n <= hi:
            raise BadInput("「%s」要在 %d 到 %d 之間" % (field["label"], lo, hi))
        return str(n)
    if kind == "text":
        # One line only: a newline would end the command and start another.
        value = re.sub(r"[\r\n]+", " ", value)
        if not value or len(value) > field.get("max", 200):
            raise BadInput("「%s」不能是空白，也不能超過 %d 字"
                           % (field["label"], field.get("max", 200)))
        return value
    raise BadInput("不認得的欄位型別：%s" % kind)


def _options(field):
    opts = field.get("options")
    return opts() if callable(opts) else (opts or [])


# --------------------------------------------------------------- choices
def map_names():
    return settings.get("bluemapMaps",
                        default=["world", "world_the_nether", "world_the_end"])


def world_names():
    return ["world", "world_nether", "world_the_end"]


def menu_names():
    d = os.path.join(PLUGINS_DIR, "DeluxeMenus", "gui_menus")
    try:
        return sorted(f[:-4] for f in os.listdir(d) if f.endswith(".yml"))
    except OSError:
        return []


BOOL = [("true", "允許／開"), ("false", "禁止／關")]
STATE = [("allow", "allow 允許"), ("deny", "deny 禁止")]

COMMON_NODES = [
    "invseeplusplus.view", "invseeplusplus.edit", "invseeplusplus.exempt",
    "stellarprotect.*", "simplyflashback.*", "bluemap.*", "worldedit.*",
    "worldguard.region.*", "luckperms.*", "spark", "floodgate.command.fwhitelist",
    "discordsrv.player", "geyser.command.list",
    "essentials.home", "essentials.sethome", "essentials.tpa", "essentials.tpaccept",
    "essentials.back", "essentials.warp", "essentials.msg", "essentials.afk",
    "chunky.*",
]

WG_FLAGS = [
    "pvp", "build", "block-break", "block-place", "use", "interact", "chest-access",
    "mob-spawning", "mob-damage", "creeper-explosion", "tnt", "other-explosion",
    "fire-spread", "lava-fire", "lightning", "entry", "exit", "invincible",
    "greeting", "farewell", "leaf-decay", "ice-melt", "snow-fall", "item-drop",
    "item-pickup", "fall-damage", "enderpearl", "vehicle-place", "vehicle-destroy",
]


# --------------------------------------------------------------- catalogue
P = F("player", "玩家", "player")

PLUGINS = [
    {"key": "bluemap", "plugin": "BlueMap", "title": "BlueMap 網頁地圖",
     "desc": "把世界算成可以在瀏覽器裡轉動的 3D 地圖。玩家走過的地方才會出現。",
     "panel": "bluemap",
     "actions": [
         A("status", "渲染狀態", [], ["bluemap"]),
         A("update", "更新地圖", [F("map", "地圖", "choice", options=map_names)],
           ["bluemap update {map}"], note="只重算有變動的部分"),
         A("force", "整張重新渲染", [F("map", "地圖", "choice", options=map_names)],
           ["bluemap force-update {map}"], danger=True, note="大地圖會跑很久"),
         A("pause", "暫停渲染", [], ["bluemap stop"]),
         A("resume", "繼續渲染", [], ["bluemap start"]),
     ]},

    {"key": "luckperms", "plugin": "LuckPerms", "title": "LuckPerms 權限",
     "desc": "決定誰能用哪些指令。OP 本來就什麼都能做，這裡管的是一般玩家。",
     "panel": "luckperms",
     "actions": [
         A("parent-add", "把玩家加進群組",
           [P, F("group", "群組", "group", suggest="groups")],
           ["lp user {player} parent add {group}"], mode="async"),
         A("parent-remove", "把玩家移出群組",
           [P, F("group", "群組", "group", suggest="groups")],
           ["lp user {player} parent remove {group}"], mode="async"),
         A("user-perm", "給玩家權限",
           [P, F("node", "權限", "node", suggest="nodes"),
            F("value", "值", "choice", options=BOOL)],
           ["lp user {player} permission set {node} {value}"], mode="async"),
         A("user-unperm", "移除玩家權限",
           [P, F("node", "權限", "node", suggest="nodes")],
           ["lp user {player} permission unset {node}"], mode="async"),
         A("group-create", "建立群組", [F("group", "群組名稱（小寫英文）", "group")],
           ["lp creategroup {group}"], mode="async"),
         A("group-perm", "給群組權限",
           [F("group", "群組", "group", suggest="groups"),
            F("node", "權限", "node", suggest="nodes"),
            F("value", "值", "choice", options=BOOL)],
           ["lp group {group} permission set {node} {value}"], mode="async"),
         A("group-unperm", "移除群組權限",
           [F("group", "群組", "group", suggest="groups"),
            F("node", "權限", "node", suggest="nodes")],
           ["lp group {group} permission unset {node}"], mode="async"),
         A("group-delete", "刪除群組", [F("group", "群組", "group", suggest="groups")],
           ["lp deletegroup {group}"], mode="async", danger=True),
     ]},

    {"key": "invsee", "plugin": "InvSeePlusPlus", "title": "InvSee++ 玩家背包",
     "desc": "查看任何玩家的背包、裝備和終界箱，離線玩家也可以。要在遊戲裡直接拿取或放入物品，用 /invsee 和 /endersee。",
     "panel": "inventory",
     "actions": [
         A("give", "給玩家物品",
           [P, F("item", "物品 ID（例如 diamond）", "item"),
            F("count", "數量", "int", min=1, max=6400, default="1")],
           # minecraft: so EssentialsX's same-named commands never pick these up.
           ["minecraft:give {player} {item} {count}"]),
         A("clear", "清空玩家背包", [P], ["minecraft:clear {player}"], danger=True,
           note="背包、裝備、副手全部清掉，無法復原"),
     ]},

    {"key": "stellarprotect", "plugin": "StellarProtect", "title": "StellarProtect 方塊紀錄",
     "desc": "記錄誰在哪裡放了、挖了、打開了什麼。這裡可以查紀錄；要還原請在遊戲裡用 /spt restore（它只接受玩家執行）。",
     "panel": "stellarprotect", "actions": []},

    {"key": "flashback", "plugin": "SimplyFlashback", "title": "SimplyFlashback 遊戲回放",
     "desc": "在伺服器端錄下玩家的遊戲過程，存成 .flashback 檔。觀看要在你的電腦裝 Flashback 模組，被錄的玩家什麼都不用裝。線上玩家每分鐘自動補上錄影、每小時切一段，超過 36 小時的檔案會被排程工作刪掉。",
     "panel": "flashback",
     "actions": [
         A("rec-start", "開始錄影", [P], ["sf record start {player}"]),
         A("rec-stop", "停止並存檔", [P], ["sf record stop {player}"]),
         A("clip-save", "存最近幾秒", [P], ["clip save {player}"],
           note="需要先對這個玩家開過 /clip start"),
         A("stats", "資源用量", [], ["sf admin stats"]),
         A("audit", "最近操作紀錄", [], ["sf admin audit"]),
         A("reload", "重新讀取設定", [], ["sf reload"]),
     ]},

    {"key": "spark", "plugin": "spark", "builtin": True, "title": "spark 效能診斷",
     "desc": "伺服器卡頓時用。產生的報告會上傳到 spark.lucko.me，用連結打開就能看圖表（這是 spark 的正常做法）。",
     "panel": "spark",
     "actions": [
         A("tick", "TPS / 每刻耗時", [], ["tps", "mspt"]),
         A("health", "產生健康報告", [], ["spark health"], mode="async", settle=6),
         A("profile", "開始效能分析",
           [F("seconds", "分析秒數", "int", min=10, max=600, default="60")],
           ["spark profiler start --timeout {seconds}"], mode="async", settle=2,
           note="時間到會自動產生報告，到時候按「重新整理」"),
         A("profile-stop", "提早結束分析", [], ["spark profiler stop"],
           mode="async", settle=6),
     ]},

    {"key": "geyser", "plugin": "Geyser-Spigot", "title": "Geyser 基岩版連線",
     "desc": "讓手機、平板、主機版玩家連進 Java 版伺服器。10/27 之後基岩版走 NetherNet，經由 Warden 加入。",
     "panel": "geyser",
     "actions": [
         A("list", "線上基岩玩家", [], ["geyser list"]),
         A("version", "版本與更新", [], ["geyser version"]),
         A("diag", "NetherNet 診斷", [], ["geyser nethernet diagnostics"]),
         A("reload", "重新讀取設定", [], ["geyser reload"], danger=True,
           note="會把所有基岩玩家踢出去"),
     ]},

    {"key": "floodgate", "plugin": "floodgate", "title": "白名單（Java＋基岩）",
     "desc": "Java 玩家用一般白名單；基岩玩家要用 Floodgate 的 fwhitelist，名字不要加前面的點。",
     "panel": "whitelist",
     "actions": [
         A("wl-on", "開啟白名單", [], ["whitelist on"]),
         A("wl-off", "關閉白名單", [], ["whitelist off"], danger=True,
           note="任何人都能進來"),
         A("java-add", "加入 Java 玩家", [P], ["whitelist add {player}"]),
         A("java-remove", "移除 Java 玩家", [P], ["whitelist remove {player}"]),
         A("be-add", "加入基岩玩家", [P], ["fwhitelist add {player}"],
           mode="async", settle=4),
         A("be-remove", "移除基岩玩家", [P], ["fwhitelist remove {player}"],
           mode="async", settle=4),
     ]},

    {"key": "discordsrv", "plugin": "DiscordSRV", "title": "DiscordSRV 聊天橋接",
     "desc": "minecraft 機器人：把遊戲聊天和 Discord #mc同步 互相轉發。",
     "panel": "discord",
     "actions": [
         A("bcast", "發公告到 Discord", [F("text", "內容", "text", max=300)],
           ["discord bcast {text}"]),
         A("resync", "重新同步身分組", [], ["discord resync"]),
         A("reload", "重新讀取設定", [], ["discord reload"]),
     ]},

    {"key": "deluxemenus", "plugin": "DeluxeMenus", "title": "DeluxeMenus 選單",
     "desc": "遊戲內的圖形選單（/menu 的管理面板、工具箱、行動工作台都是它畫的）。",
     "panel": None,
     "actions": [
         A("list", "列出選單", [], ["dm list"]),
         A("open", "幫玩家打開選單",
           [F("menu", "選單", "choice", options=menu_names), P],
           ["dm open {menu} {player}"]),
         A("reload", "重新讀取選單", [], ["dm reload"]),
     ]},

    {"key": "panelkey", "plugin": "PanelKey", "title": "PanelKey 管理面板",
     "desc": "自製外掛。玩家指令：/pmenu 玩家選單（回家、傳送請求、回上一個位置等，一般玩家也能用；沒有管理權限的人按 Shift+F 也會開到這裡）、/spawn 回出生點、/tpamenu 選人送傳送請求。管理員：/menu 管理面板、/mobile 行動工作台、/givetarget 指定工具箱給誰。",
     "panel": None,
     "actions": [
         A("admin", "幫玩家打開管理面板", [P], ["dm open admin_panel {player}"]),
         A("toolbox", "幫玩家打開工具箱", [P], ["dm open toolbox {player}"]),
         A("stations", "幫玩家打開行動工作台", [P], ["dm open stations {player}"]),
         A("player-menu", "幫玩家打開玩家選單", [P], ["dm open player_menu {player}"]),
     ]},

    {"key": "placeholderapi", "plugin": "PlaceholderAPI", "title": "PlaceholderAPI",
     "desc": "讓其他外掛能顯示玩家名字、狀態之類的變數。通常不用動它。",
     "panel": None,
     "actions": [
         A("list", "已啟用的擴充", [], ["papi list"]),
         A("parse", "測試變數",
           [P, F("text", "變數（例如 %player_name%）", "text", max=200)],
           ["papi parse {player} {text}"]),
         A("reload", "重新讀取", [], ["papi reload"]),
     ]},

    {"key": "worldguard", "plugin": "WorldGuard", "title": "WorldGuard 區域保護",
     "desc": "保護指定區域不被破壞。新增區域要在遊戲裡用 //wand 選範圍後打 /rg define 名稱；這裡可以改旗標、成員和優先順序。",
     "panel": "worldguard",
     "actions": [
         A("flag", "設定旗標",
           [F("world", "世界", "choice", options=world_names),
            F("region", "區域（全世界用 __global__）", "region", suggest="regions"),
            F("flag", "旗標", "flag", suggest="flags"),
            F("value", "值", "choice", options=STATE)],
           ["rg flag -w {world} {region} {flag} {value}", "rg save -w {world}"],
           mode="async", settle=2.5),
         A("unflag", "清除旗標",
           [F("world", "世界", "choice", options=world_names),
            F("region", "區域", "region", suggest="regions"),
            F("flag", "旗標", "flag", suggest="flags")],
           ["rg flag -w {world} {region} {flag}", "rg save -w {world}"],
           mode="async", settle=2.5),
         A("member", "加入成員",
           [F("world", "世界", "choice", options=world_names),
            F("region", "區域", "region", suggest="regions"), P],
           ["rg addmember -w {world} {region} {player}", "rg save -w {world}"],
           mode="async", settle=2.5),
         A("owner", "加入擁有者",
           [F("world", "世界", "choice", options=world_names),
            F("region", "區域", "region", suggest="regions"), P],
           ["rg addowner -w {world} {region} {player}", "rg save -w {world}"],
           mode="async", settle=2.5),
         A("unmember", "移除成員",
           [F("world", "世界", "choice", options=world_names),
            F("region", "區域", "region", suggest="regions"), P],
           ["rg removemember -w {world} {region} {player}", "rg save -w {world}"],
           mode="async", settle=2.5),
         A("priority", "設定優先順序",
           [F("world", "世界", "choice", options=world_names),
            F("region", "區域", "region", suggest="regions"),
            F("priority", "優先順序", "int", min=-100, max=1000, default="0")],
           ["rg setpriority -w {world} {region} {priority}", "rg save -w {world}"],
           mode="async", settle=2.5),
         A("remove", "刪除區域",
           [F("world", "世界", "choice", options=world_names),
            F("region", "區域", "region", suggest="regions")],
           ["rg remove -w {world} {region}", "rg save -w {world}"],
           mode="async", settle=2.5, danger=True),
     ]},

    {"key": "chunky", "plugin": "Chunky", "title": "Chunky 預先生成地形",
     "desc": "趁沒人在玩的時候先把一片範圍的地形生成好，之後跑圖就不會卡。以出生點為中心、正方形範圍；生成中很吃效能，可以隨時暫停。",
     "panel": None,
     "actions": [
         A("progress", "目前進度", [], ["chunky progress"]),
         A("start", "開始預先生成",
           [F("world", "世界", "choice", options=world_names),
            F("radius", "半徑（格）", "int", min=100, max=20000, default="2000")],
           ["chunky world {world}", "chunky spawn", "chunky radius {radius}", "chunky start"],
           note="半徑 2000 約是 4000×4000 格；跑完要好幾個小時"),
         A("confirm", "確認覆蓋舊任務", [], ["chunky confirm"],
           note="同一個世界已經有未完成的任務時，開始會先要求確認"),
         A("pause", "暫停", [], ["chunky pause"]),
         A("continue", "繼續", [], ["chunky continue"]),
         A("cancel", "取消任務", [], ["chunky cancel"], danger=True,
           note="已經生成的地形會留著，只是不再往下跑"),
     ]},

    {"key": "essentials", "plugin": "Essentials", "title": "EssentialsX 常用指令",
     "desc": "/home、/tpa、/back、/warp、私訊、AFK 等常用指令。一般玩家能用哪些，要在 LuckPerms 給 essentials.* 開頭的權限。",
     "panel": None,
     "actions": [
         A("seen", "查玩家最後上線", [P], ["seen {player}"]),
         A("bcast", "全服公告", [F("text", "內容", "text", max=200)],
           ["broadcast {text}"]),
         A("mute", "禁言／解除禁言", [P], ["mute {player}"],
           note="對已經禁言的人再按一次就會解除"),
         A("version", "版本", [], ["essentials version"]),
         A("reload", "重新讀取設定", [], ["essentials reload"]),
     ]},

    {"key": "fpp", "plugin": "FakePlayerPlugin", "title": "FakePlayerPlugin 假人",
     "desc": "在伺服器上放假人，玩家下線後假人會留著讓農場、刷怪塔繼續跑（假人周圍的區塊會保持載入）。一般玩家在遊戲裡打 /fpp spawn 可放 1 個；重啟後假人會自動回來。",
     "panel": None,
     "actions": [
         A("list", "列出假人", [], ["fpp list"]),
         A("spawn", "在指定位置放假人",
           [F("name", "假人名字", "player"),
            F("world", "世界", "choice", options=world_names),
            F("x", "X", "int", min=-30000000, max=30000000, default="-79"),
            F("y", "Y", "int", min=-64, max=320, default="128"),
            F("z", "Z", "int", min=-30000000, max=30000000, default="43")],
           ["fpp spawn --name {name} --location {x} {y} {z} {world}"]),
         A("despawn", "移除假人", [F("name", "假人名字", "player")],
           ["fpp despawn {name}"]),
         A("despawn-all", "移除全部假人", [], ["fpp despawn all"], danger=True),
         A("reload", "重新讀取設定", [], ["fpp reload"]),
     ]},

    {"key": "worldedit", "plugin": "WorldEdit", "title": "WorldEdit 大範圍編輯",
     "desc": "建築用的工具，幾乎都要在遊戲裡操作：拿 //wand 選兩個角，再用 //set、//copy、//paste。",
     "panel": None,
     "actions": [
         A("version", "版本", [], ["we version"]),
         A("reload", "重新讀取設定", [], ["we reload"]),
     ]},
]

BY_KEY = {p["key"]: p for p in PLUGINS}


# ----------------------------------------------------------- plugin status
_STATUS = {"at": 0.0, "data": {}}


def plugin_status():
    """{server plugin name: {"version", "enabled"}} from the log and RCON."""
    if time.time() - _STATUS["at"] < 15 and _STATUS["data"]:
        return _STATUS["data"]
    versions, disabled = {}, set()
    log_path = os.path.join(SERVER_DIR, "logs", "latest.log")
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        lines = []
    for ln in lines:
        # Paper prints the plugin list as a bare continuation line:
        # " - BlueMap (5.29), DeluxeMenus (1.14.1-Release), ..."
        if ln.startswith(" - ") and "(" in ln:
            for name, ver in re.findall(r"([A-Za-z0-9_\-+. ]+?) \(([^()]+(?:\([^)]*\))?[^()]*)\)",
                                        ln[3:]):
                versions[name.strip(" ,")] = ver
        m = re.search(r"\[([^\]]+)\] Disabling \1 v", ln)
        if m:
            disabled.add(m.group(1))
        if "Stopping server" in ln:
            disabled.clear()
    ok, out = rcon.execute(["plugins"]) if rcon else (False, "")
    loaded = set()
    if ok:
        body = out.split("Bukkit Plugins:", 1)[-1]
        loaded = {n.strip(" -\n") for n in re.split(r"[,\n]", body) if n.strip(" -\n")}
    data = {}
    for p in PLUGINS:
        name = p["plugin"]
        if p.get("builtin"):
            # Part of Paper itself, so never on the plugin list.
            data[name] = {"version": "Paper 內建", "enabled": bool(ok), "known": bool(ok)}
            continue
        data[name] = {"version": versions.get(name, ""),
                      "enabled": name in loaded and name not in disabled,
                      "known": bool(ok)}
    _STATUS.update(at=time.time(), data=data)
    return data


def catalogue():
    """What the page needs to draw every panel - no secrets in here."""
    st = plugin_status()
    out = []
    for p in PLUGINS:
        actions = []
        for a in p["actions"]:
            fields = []
            for f in a["fields"]:
                g = {k: v for k, v in f.items() if k != "options"}
                if f["kind"] == "choice":
                    g["options"] = [o if isinstance(o, (list, tuple)) else (o, o)
                                    for o in _options(f)]
                fields.append(g)
            actions.append({"id": a["id"], "label": a["label"], "fields": fields,
                            "danger": a["danger"], "note": a["note"],
                            "async": a["mode"] == "async"})
        s = st.get(p["plugin"], {})
        out.append({"key": p["key"], "plugin": p["plugin"], "title": p["title"],
                    "desc": p["desc"], "panel": p["panel"], "actions": actions,
                    "version": s.get("version", ""), "enabled": s.get("enabled"),
                    "known": s.get("known", False)})
    return {"plugins": out, "players": known_players(),
            "suggest": {"nodes": COMMON_NODES, "flags": WG_FLAGS}}


def run_action(key, action_id, args):
    p = BY_KEY.get(key)
    if not p:
        raise BadInput("不認得的外掛：%s" % key)
    action = next((a for a in p["actions"] if a["id"] == action_id), None)
    if not action:
        raise BadInput("不認得的動作：%s" % action_id)
    values = {f["name"]: _clean(f, (args or {}).get(f["name"]))
              for f in action["fields"]}
    commands = [c.format(**values) for c in action["cmds"]]
    ok, replies = rcon.execute_each(commands)
    text = "\n".join(r for r in replies if r).strip()
    if action["mode"] == "async":
        time.sleep(action["settle"])
        if ok and not text:
            text = "已送出。這個外掛不會把結果回傳給主控台，請看下方最新資料確認。"
    return {"ok": ok, "output": text or "（伺服器沒有回傳文字）",
            "commands": commands, "refresh": True}


# ------------------------------------------------------------------ players
def _usercache():
    try:
        with open(os.path.join(SERVER_DIR, "usercache.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return []


def known_players():
    return sorted({e["name"] for e in _usercache() if e.get("name")},
                  key=str.lower)


def online_players():
    # minecraft:list: EssentialsX's /list is translated and grouped.
    ok, out = rcon.execute(["minecraft:list"])
    if not ok or ":" not in out:
        return []
    return [n.strip() for n in out.split(":", 1)[1].split(",") if n.strip()]


# -------------------------------------------------------------- item names
_ZH = {"names": None}
_JAR = {"zip": None, "en": None, "icons": {}}


def _client_jar():
    if _JAR["zip"] is None:
        d = os.path.join(SERVER_DIR, "bluemap")
        jars = sorted(f for f in os.listdir(d) if f.startswith("minecraft-client")
                      and f.endswith(".jar")) if os.path.isdir(d) else []
        _JAR["zip"] = zipfile.ZipFile(os.path.join(d, jars[-1])) if jars else False
    return _JAR["zip"] or None


def _en_names():
    if _JAR["en"] is None:
        jar = _client_jar()
        try:
            _JAR["en"] = json.loads(jar.read("assets/minecraft/lang/en_us.json")) if jar else {}
        except KeyError:
            _JAR["en"] = {}
    return _JAR["en"]


def _load_zh_names():
    """zh_tw is not in the client jar; it is one asset on Mojang's CDN."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, "lang-zh_tw.json")
    try:
        with open(path, encoding="utf-8") as fh:
            _ZH["names"] = json.load(fh)
            return
    except (OSError, ValueError):
        pass

    def get(url):
        return urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                      timeout=30).read()
    try:
        jar = _client_jar()
        version = json.loads(jar.read("version.json"))["id"] if jar else None
        manifest = json.loads(get(
            "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"))
        entry = next(v for v in manifest["versions"] if v["id"] == version)
        index = json.loads(get(json.loads(get(entry["url"]))["assetIndex"]["url"]))
        h = index["objects"]["minecraft/lang/zh_tw.json"]["hash"]
        data = get("https://resources.download.minecraft.net/%s/%s" % (h[:2], h))
        _ZH["names"] = json.loads(data)
        with open(path, "wb") as fh:
            fh.write(data)
    except Exception:
        _ZH["names"] = {}


def item_name(item_id):
    short = item_id.split(":", 1)[-1]
    for table in (_ZH["names"] or {}, _en_names()):
        for kind in ("item", "block"):
            key = "%s.minecraft.%s" % (kind, short)
            if key in table:
                return table[key]
    return short.replace("_", " ")


SUFFIXES = ("_stairs", "_slab", "_wall", "_fence_gate", "_fence",
            "_pressure_plate", "_button")


def item_icon(item_id):
    """PNG bytes for an item, from the client jar's own textures."""
    short = item_id.split(":", 1)[-1]
    if not re.fullmatch(r"[a-z0-9_]{1,60}", short):
        return None
    cache = _JAR["icons"]
    if short in cache:
        return cache[short]
    jar = _client_jar()
    found = None
    if jar:
        base = short
        for suf in SUFFIXES:
            if short.endswith(suf):
                base = short[:-len(suf)]
                break
        candidates = [("item", short), ("block", short), ("block", short + "_top"),
                      ("block", short + "_front"), ("block", short + "_side"),
                      ("block", base), ("block", base + "_planks"),
                      ("block", base + "s"), ("block", base + "_block")]
        for folder, name in candidates:
            try:
                found = jar.read("assets/minecraft/textures/%s/%s.png" % (folder, name))
                break
            except KeyError:
                continue
    cache[short] = found
    return found


# --------------------------------------------------------------- inventory
EQUIP_SLOTS = [("head", "頭盔"), ("chest", "胸甲"), ("legs", "護腿"),
               ("feet", "靴子"), ("offhand", "副手")]


def _text(v):
    if isinstance(v, str):
        try:
            return _text(json.loads(v))
        except ValueError:
            return v
    if isinstance(v, dict):
        return (v.get("text") or v.get("translate") or "") + "".join(
            _text(x) for x in v.get("extra", []))
    if isinstance(v, list):
        return "".join(_text(x) for x in v)
    return str(v)


def _item(d):
    comps = d.get("components") or {}
    ench = comps.get("minecraft:enchantments") or {}
    if isinstance(ench, dict) and "levels" in ench:
        ench = ench["levels"]
    enchants = []
    for k, lvl in (ench.items() if isinstance(ench, dict) else []):
        short = k.split(":", 1)[-1]
        label = ((_ZH["names"] or {}).get("enchantment.minecraft." + short)
                 or _en_names().get("enchantment.minecraft." + short)
                 or short.replace("_", " "))
        enchants.append("%s %s" % (label, lvl))
    return {"id": d.get("id", ""), "name": item_name(d.get("id", "")),
            "count": d.get("count", 1),
            "custom": _text(comps["minecraft:custom_name"]) if "minecraft:custom_name" in comps else "",
            "damage": comps.get("minecraft:damage"),
            "enchants": enchants}


def inventory(player):
    if not re.fullmatch(PATTERNS["player"], player or ""):
        raise BadInput("玩家名稱格式不對")
    entry = next((e for e in _usercache() if e["name"].lower() == player.lower()), None)
    if not entry:
        raise BadInput("找不到這個玩家（還沒進過伺服器？）")
    online = player.lower() in (n.lower() for n in online_players())
    if online:
        # The .dat file is only as fresh as the last save.
        rcon.execute(["save-all"])
        time.sleep(1.2)
    path = os.path.join(SERVER_DIR, "world", "players", "data", entry["uuid"] + ".dat")
    if not os.path.exists(path):
        raise BadInput("找不到這個玩家的存檔")
    d = nbt.plain(nbt.load_nbt(path))
    inv = {int(i.get("Slot", -1)): _item(i) for i in d.get("Inventory", [])}
    ender = {int(i.get("Slot", -1)): _item(i) for i in d.get("EnderItems", [])}
    eq = d.get("equipment") or {}
    pos = d.get("Pos") or [0, 0, 0]
    return {
        "player": entry["name"], "online": online,
        "saved": time.strftime("%Y-%m-%d %H:%M:%S",
                               time.localtime(os.path.getmtime(path))),
        "selected": d.get("SelectedItemSlot", 0),
        "health": round(float(d.get("Health", 0)), 1),
        "food": d.get("foodLevel"), "level": d.get("XpLevel"),
        "mode": {0: "生存", 1: "創造", 2: "冒險", 3: "旁觀"}.get(d.get("playerGameType"), "?"),
        "where": "%s  %d, %d, %d" % (d.get("Dimension", "").split(":")[-1],
                                     pos[0], pos[1], pos[2]),
        "slots": {str(k): v for k, v in inv.items()},
        "equipment": [{"slot": k, "label": lbl, "item": _item(eq[k]) if k in eq else None}
                      for k, lbl in EQUIP_SLOTS],
        "ender": {str(k): v for k, v in ender.items()},
    }


# -------------------------------------------------------------- LuckPerms
def luckperms_data():
    name = "webconsole-%d" % int(time.time() * 1000)
    path = os.path.join(PLUGINS_DIR, "LuckPerms", name + ".json.gz")
    rcon.execute(["lp export " + name])
    for _ in range(40):
        if os.path.exists(path):
            break
        time.sleep(0.25)
    else:
        return {"error": "LuckPerms 沒有產生匯出檔（伺服器在跑嗎？）"}
    # The export is written in one go but may still be closing.
    for _ in range(10):
        try:
            data = json.load(gzip.open(path))
            break
        except (OSError, EOFError, ValueError):
            time.sleep(0.3)
    else:
        return {"error": "讀不到 LuckPerms 匯出檔"}
    try:
        os.remove(path)
    except OSError:
        pass

    def nodes(lst):
        return [{"key": n.get("key"), "value": n.get("value", True),
                 "context": n.get("context") or {}} for n in lst or []]
    groups = [{"name": g, "nodes": nodes(v.get("nodes"))}
              for g, v in sorted(data.get("groups", {}).items())]
    users = [{"uuid": u, "name": v.get("username", u[:8]),
              "primary": v.get("primaryGroup", "default"),
              "nodes": nodes(v.get("nodes"))}
             for u, v in data.get("users", {}).items()]
    users.sort(key=lambda u: u["name"].lower())
    return {"groups": groups, "users": users}


# ------------------------------------------------------------- WorldGuard
def _yaml_scalar(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "'\"":
        return s[1:-1]
    if s.startswith("{") and s.endswith("}"):
        out = {}
        for part in _split_flow(s[1:-1]):
            if ":" in part:
                k, v = part.split(":", 1)
                out[_yaml_scalar(k)] = _yaml_scalar(v)
        return out
    if s.startswith("[") and s.endswith("]"):
        return [_yaml_scalar(p) for p in _split_flow(s[1:-1]) if p.strip()]
    return s


def _split_flow(s):
    parts, depth, cur, quote = [], 0, "", None
    for ch in s:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
            continue
        cur += ch
    if cur.strip():
        parts.append(cur)
    return parts


def parse_simple_yaml(text):
    """Enough YAML for WorldGuard's regions.yml: block maps and lists, plus
    flow-style maps/lists as values. Not a general parser."""
    lines = [(len(l) - len(l.lstrip(" ")), l.strip()) for l in text.splitlines()
             if l.strip() and not l.strip().startswith("#")]
    pos = 0

    def seq():
        # Items may sit at the key's own indent ("players:\n- a") or deeper.
        nonlocal pos
        items, lvl = [], lines[pos][0]
        while pos < len(lines) and lines[pos][0] == lvl and lines[pos][1].startswith("- "):
            items.append(_yaml_scalar(lines[pos][1][2:]))
            pos += 1
        return items

    def mapping():
        nonlocal pos
        out, lvl = {}, lines[pos][0]
        while pos < len(lines) and lines[pos][0] == lvl and not lines[pos][1].startswith("- "):
            key, _, rest = lines[pos][1].partition(":")
            pos += 1
            if rest.strip():
                out[_yaml_scalar(key)] = _yaml_scalar(rest)
            elif pos < len(lines) and lines[pos][1].startswith("- ") and lines[pos][0] >= lvl:
                out[_yaml_scalar(key)] = seq()
            elif pos < len(lines) and lines[pos][0] > lvl:
                out[_yaml_scalar(key)] = mapping()
            else:
                out[_yaml_scalar(key)] = None
        return out
    return mapping() if lines else {}


def worldguard_data():
    worlds = []
    for w in world_names():
        path = os.path.join(PLUGINS_DIR, "WorldGuard", "worlds", w, "regions.yml")
        regions = []
        try:
            with open(path, encoding="utf-8") as fh:
                doc = parse_simple_yaml(fh.read())
        except OSError:
            doc = {}
        for rid, r in ((doc or {}).get("regions") or {}).items():
            r = r or {}

            def people(k):
                v = r.get(k) or {}
                return (v.get("players") or []) + (v.get("groups") or []) if isinstance(v, dict) else []
            regions.append({"id": rid, "type": r.get("type", ""),
                            "priority": r.get("priority", "0"),
                            "min": r.get("min"), "max": r.get("max"),
                            "flags": r.get("flags") or {},
                            "owners": people("owners"), "members": people("members")})
        worlds.append({"world": w, "regions": sorted(regions, key=lambda x: x["id"])})
    return {"worlds": worlds}


# ---------------------------------------------------------- StellarProtect
ACTIONS = {
    0: "破壞方塊", 1: "放置方塊", 2: "使用方塊", 3: "丟出物品", 4: "撿起物品",
    5: "熔爐取出", 6: "熔爐放入", 7: "合成", 8: "作物生長", 9: "擊殺生物",
    10: "互動", 11: "馴服", 12: "繁殖", 13: "聊天", 14: "指令", 15: "倒出桶子",
    16: "裝滿桶子", 17: "容器存取", 18: "使用物品", 19: "上下線", 20: "編輯告示牌",
    21: "附魔", 23: "死亡", 24: "騎乘", 26: "掛畫／物品展示框", 27: "鍛造",
    29: "修理", 30: "射擊", 31: "不死圖騰", 32: "傳送", 33: "吃喝", 34: "切換模式",
    35: "經驗", 37: "裝飾變更", 38: "放入物品", 39: "取出物品", 40: "樹木生長",
    41: "方塊擴散", 42: "盔甲座", 43: "拴繩", 44: "方塊消退", 45: "方塊燒毀",
    46: "方塊形成", 47: "發射器", 48: "釀造", 87: "背包快照",
}


def stellarprotect_query(args):
    path = os.path.join(PLUGINS_DIR, "StellarProtect", "StellarProtect.db")
    if not os.path.exists(path):
        return {"error": "找不到 StellarProtect 的資料庫"}
    hours = float(_clean(F("hours", "時間範圍（小時）", "int", min=1, max=24 * 365),
                         args.get("hours") or "24"))
    where, params = ["l.created_at >= ?"], []
    since = time.time() - hours * 3600
    player = (args.get("player") or "").strip()
    if player:
        _clean(F("player", "玩家", "player"), player)
        where.append("(lower(p.name) = lower(?) OR lower(p.realname) = lower(?))")
        params += [player, player]
    action = (args.get("action") or "").strip()
    if action:
        if not action.isdigit() or int(action) not in ACTIONS:
            raise BadInput("不認得的動作類型")
        where.append("l.action_type = ?")
        params.append(int(action))
    world = (args.get("world") or "").strip()
    if world:
        if world not in world_names():
            raise BadInput("不認得的世界")
        where.append("w.name = ?")
        params.append(world)
    if (args.get("x") or "").strip():
        x, y, z = (float(_clean(F(k, k, "int", min=-30000000, max=30000000), args.get(k)))
                   for k in ("x", "y", "z"))
        r = float(_clean(F("radius", "半徑", "int", min=1, max=500), args.get("radius") or "10"))
        where.append("l.x BETWEEN ? AND ? AND l.y BETWEEN ? AND ? AND l.z BETWEEN ? AND ?")
        params += [x - r, x + r, y - r, y + r, z - r, z + r]

    con = sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=5)
    try:
        # created_at is milliseconds in this schema; detect rather than assume.
        newest = con.execute("select max(created_at) from log_entries").fetchone()[0] or 0
        scale = 1000 if newest > 10 ** 11 else 1
        params.insert(0, since * scale)
        sql = ("SELECT l.created_at, coalesce(p.realname, p.name, '?'), w.name, l.x, l.y, l.z, "
               "l.action_type, l.restored, bt.block_data, obt.block_data, l.amount, "
               "l.entity_type, l.extra_json FROM log_entries l "
               "LEFT JOIN players p ON p.id = l.player_id "
               "LEFT JOIN worlds w ON w.id = l.world_id "
               "LEFT JOIN block_templates bt ON bt.id = l.block_id "
               "LEFT JOIN block_templates obt ON obt.id = l.old_block_id "
               "WHERE " + " AND ".join(where) +
               " ORDER BY l.created_at DESC LIMIT 300")
        rows = con.execute(sql, params).fetchall()
        total = con.execute("select count(*) from log_entries").fetchone()[0]
    finally:
        con.close()

    def block(b):
        if not b:
            return ""
        bid = re.split(r"[\[{]", b, 1)[0]
        return item_name(bid if ":" in bid else "minecraft:" + bid)
    out = []
    for (t, who, w, x, y, z, act, restored, blk, old, amount, ent, extra) in rows:
        target = block(blk) or block(old) or (ent or "").split(":")[-1].replace("_", " ")
        out.append({"time": time.strftime("%m-%d %H:%M:%S", time.localtime(t / scale)),
                    "player": who, "world": w or "",
                    "pos": "%d, %d, %d" % (x or 0, y or 0, z or 0),
                    "action": ACTIONS.get(act, "類型 %s" % act), "target": target,
                    "amount": amount or "", "restored": bool(restored)})
    return {"rows": out, "total": total, "actions": sorted(ACTIONS.items())}


# ------------------------------------------------------------ files: replays
FILE_KINDS = {
    "replay": os.path.join(PLUGINS_DIR, "SimplyFlashback", "replays"),
    "clip": os.path.join(PLUGINS_DIR, "SimplyFlashback", "clips"),
}


def list_files(kind):
    base = FILE_KINDS[kind]
    out = []
    for root, _, files in os.walk(base):
        for f in files:
            full = os.path.join(root, f)
            out.append({"name": os.path.relpath(full, base).replace("\\", "/"),
                        "mb": round(os.path.getsize(full) / 1048576, 2),
                        "time": time.strftime("%Y-%m-%d %H:%M",
                                              time.localtime(os.path.getmtime(full))),
                        "_m": os.path.getmtime(full)})
    out.sort(key=lambda e: -e["_m"])
    for e in out:
        e.pop("_m")
    return out


def read_download(kind, name):
    """Only a file that a listing would show - never a path from the request."""
    if kind not in FILE_KINDS:
        raise BadInput("不認得的檔案類型")
    if name not in {e["name"] for e in list_files(kind)}:
        raise BadInput("找不到這個檔案")
    path = os.path.join(FILE_KINDS[kind], *name.split("/"))
    with open(path, "rb") as fh:
        return os.path.basename(path), fh.read()


def flashback_data():
    return {"replays": list_files("replay"), "clips": list_files("clip")}


# ----------------------------------------------------------------- spark
def spark_data():
    path = os.path.join(PLUGINS_DIR, "spark", "activity.json")
    try:
        with open(path, encoding="utf-8") as fh:
            items = json.load(fh)
    except (OSError, ValueError):
        items = []
    kinds = {"Health report": "健康報告", "Profiler": "效能分析",
             "Heap dump summary": "記憶體摘要"}
    out = []
    for e in items[:15]:
        d = e.get("data") or {}
        out.append({"time": time.strftime("%m-%d %H:%M", time.localtime(e.get("time", 0) / 1000)),
                    "type": kinds.get(e.get("type"), e.get("type", "")),
                    "by": (e.get("user") or {}).get("name", ""),
                    "url": d.get("value") if d.get("type") == "url" else "",
                    "file": d.get("value") if d.get("type") == "file" else ""})
    ok, reply = rcon.execute(["tps", "mspt"])
    return {"activity": out, "tick": reply if ok else ""}


# ------------------------------------------------------------- whitelist
FLOODGATE_PREFIX = "00000000-0000-0000-0009-"


def whitelist_data():
    try:
        with open(os.path.join(SERVER_DIR, "whitelist.json"), encoding="utf-8") as fh:
            entries = json.load(fh)
    except (OSError, ValueError):
        entries = []
    on = None
    try:
        with open(os.path.join(SERVER_DIR, "server.properties"), encoding="utf-8") as fh:
            for ln in fh:
                if ln.startswith("white-list="):
                    on = ln.strip().split("=", 1)[1] == "true"
    except OSError:
        pass
    return {"enabled": on,
            "entries": [{"name": e.get("name", "?"),
                         "bedrock": e.get("uuid", "").startswith(FLOODGATE_PREFIX)}
                        for e in entries]}


# ------------------------------------------------------- log-based panels
def _log_lines(pattern, limit=12):
    try:
        with open(os.path.join(SERVER_DIR, "logs", "latest.log"),
                  encoding="utf-8", errors="replace") as fh:
            hits = [ln.rstrip() for ln in fh if re.search(pattern, ln)]
    except OSError:
        hits = []
    return hits[-limit:]


def geyser_data():
    join = ""
    for ln in _log_lines(r"Players can join at"):
        m = re.search(r"join at (\S+)", ln)
        if m:
            join = m.group(1)
    ok, reply = rcon.execute(["geyser list"])
    # The log only knows Warden's automatic address; players are given the
    # custom domain from config.json.
    custom = settings.get("bedrock", "host", default="")
    return {"join": custom or join, "auto": join if custom else "",
            "players": reply if ok else "",
            "log": _log_lines(r"Geyser-Spigot\].*(NetherNet|NXS|signaling|UDP|Warden)|WARN.*Geyser", 8)}


def discord_data():
    channels, console = "", ""
    try:
        with open(os.path.join(PLUGINS_DIR, "DiscordSRV", "config.yml"), encoding="utf-8") as fh:
            for ln in fh:
                if ln.startswith("Channels:"):
                    channels = ln.split(":", 1)[1].strip()
                if ln.startswith("DiscordConsoleChannelId:"):
                    console = ln.split(":", 1)[1].strip().strip('"')
    except OSError:
        pass
    linked = 0
    aof = os.path.join(PLUGINS_DIR, "DiscordSRV", "accounts.aof")
    try:
        with open(aof, encoding="utf-8", errors="replace") as fh:
            linked = sum(1 for ln in fh if ln.strip())
    except OSError:
        pass
    return {"channels": channels, "console": console or "（未使用）", "linked": linked,
            "log": _log_lines(r"\[DiscordSRV\]", 8)}


def bluemap_data():
    ok, reply = rcon.execute(["bluemap"])
    return {"status": reply if ok else "", "url": settings.get("mapUrl", default="")}


PANEL_DATA = {
    "luckperms": lambda a: luckperms_data(),
    "worldguard": lambda a: worldguard_data(),
    "stellarprotect": stellarprotect_query,
    "flashback": lambda a: flashback_data(),
    "spark": lambda a: spark_data(),
    "whitelist": lambda a: whitelist_data(),
    "geyser": lambda a: geyser_data(),
    "discord": lambda a: discord_data(),
    "bluemap": lambda a: bluemap_data(),
    "inventory": lambda a: inventory(a.get("player", "")),
}


def panel_data(panel, args):
    fn = PANEL_DATA.get(panel)
    if not fn:
        raise BadInput("這個面板沒有資料")
    return fn(args or {})
