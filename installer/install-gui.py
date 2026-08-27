#!/usr/bin/env python3
"""Graphical installer for the Minecraft Server Toolkit.

Automates what docs/INSTALL.md asks you to do by hand: lay down the toolkit,
fetch a Paper build, switch RCON on, write config.json, register the scheduled
tasks, open the firewall for the LAN console and drop shortcuts on the desktop.

Everything is one screen rather than a wizard - the whole install is a dozen
decisions and it is easier to review them together than to page through them.

Built into a single .exe by build_exe.py; running it as a plain script works
too, in which case it uses the files sitting next to the repository root.
"""

import ctypes
import json
import os
import queue
import re
import secrets
import shutil
import string
import subprocess
import sys
import threading
import tkinter as tk
import urllib.request
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "Minecraft Server Toolkit 安裝程式"
PAPER_API = "https://fill.papermc.io/v3/projects/paper"
UA = {"User-Agent": "mc-toolkit-installer"}
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Directories Windows' Controlled Folder Access protects by default. Writes
# there fail silently, so an install under one of them looks like it worked
# and then the server dies with no error at all.
PROTECTED = ("documents", "pictures", "desktop", "videos", "music")


def bundle_dir():
    """Where the payload (scripts/, windows/) lives right now."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def enable_dpi_awareness():
    """Tell Windows we draw at real pixels - before any window exists.

    Called after the root window is created it has no effect, and asking for
    awareness without then scaling the fonts is worse than not asking at all:
    Windows stops magnifying the app, so on a 253% display every control comes
    out roughly a third of its intended size.
    """
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)      # per-monitor v2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()       # older fallback
        except Exception:
            pass


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run(cmd, timeout=120):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=NO_WINDOW, encoding="utf-8",
                           errors="replace")
        return p.returncode == 0, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return False, str(exc)


def powershell(script, timeout=180):
    return run(["powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-Command", script], timeout)


def java_version():
    ok, out = run(["java", "-version"], timeout=30)
    if not ok and "version" not in out:
        return None, out.strip()[:80]
    m = re.search(r'version "(\d+)', out)
    return (int(m.group(1)) if m else None), out.splitlines()[0] if out else ""


def controlled_folder_access():
    ok, out = powershell("(Get-MpPreference).EnableControlledFolderAccess",
                         timeout=60)
    return out.strip().startswith("1") if ok else None


def under_protected(path):
    low = os.path.abspath(path).lower()
    home = os.path.expanduser("~").lower()
    return low.startswith(home) and any(
        low.startswith(os.path.join(home, p)) for p in PROTECTED)


def fetch_json(url):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=30).read())


def paper_versions():
    data = fetch_json(PAPER_API)
    out = []
    versions = data.get("versions", {})
    if isinstance(versions, dict):
        for group in versions.values():
            out.extend(group)
    elif isinstance(versions, list):
        out = list(versions)
    # The API lists newest first, both across groups and within them, so the
    # order is kept as-is and the combobox defaults to the newest release.
    # Pre-releases are filtered out: "-rc-" is not what an install should
    # land on by default.
    stable = [v for v in out if "-" not in v]
    return stable or out


def paper_download(version):
    builds = fetch_json("%s/versions/%s/builds" % (PAPER_API, version))
    if not isinstance(builds, list) or not builds:
        raise RuntimeError("這個版本沒有可用的 build")
    for build in builds:
        if build.get("channel") == "STABLE":
            chosen = build
            break
    else:
        chosen = builds[0]
    downloads = chosen.get("downloads", {})
    entry = downloads.get("server:default") or next(iter(downloads.values()))
    return entry["url"], entry["name"], chosen.get("id")


def make_password(n=24):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


class Installer(tk.Tk):
    PAD = 10        # replaced with a scaled value in __init__

    def px(self, n):
        """A design pixel in this display's real pixels."""
        return int(n * self.scale)

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)

        # The process is DPI aware, so the window is measured in real pixels.
        # Tk's point scaling and every hard-coded pixel size have to follow the
        # display scale or the whole UI comes out tiny.
        dpi = self.winfo_fpixels("1i")
        self.scale = dpi / 96.0
        self.tk.call("tk", "scaling", dpi / 72.0)
        # Clamp to the screen: at 2.25x a 780-pixel design is 1755 tall, which
        # overflows a 1800-pixel display and hides the install button.
        want_w, want_h = self.px(860), self.px(760)
        max_w = int(self.winfo_screenwidth() * 0.92)
        max_h = int(self.winfo_screenheight() * 0.88)
        self.geometry("%dx%d" % (min(want_w, max_w), min(want_h, max_h)))
        self.minsize(min(self.px(700), max_w), min(self.px(560), max_h))
        self.PAD = self.px(10)

        try:
            ttk.Style().theme_use("vista")
        except tk.TclError:
            pass

        self.q = queue.Queue()
        self.busy = False
        self._build()
        self.after(80, self._drain)
        threading.Thread(target=self._check_environment, daemon=True).start()

    # ------------------------------------------------------------------ ui
    def _build(self):
        root = ttk.Frame(self, padding=self.PAD)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="Minecraft Server Toolkit",
                  font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(root, foreground="#666",
                  text="自動完成 INSTALL.md 的安裝流程").pack(anchor="w",
                                                             pady=(0, 8))

        # --- environment ---
        env = ttk.LabelFrame(root, text=" 環境檢查 ", padding=self.PAD)
        env.pack(fill="x", pady=4)
        self.env_labels = {}
        for key, text in (("java", "Java"), ("cfa", "受控資料夾存取"),
                          ("admin", "系統管理員權限")):
            row = ttk.Frame(env)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=text, width=16).pack(side="left")
            lbl = ttk.Label(row, text="檢查中…", foreground="#888")
            lbl.pack(side="left")
            self.env_labels[key] = lbl

        # --- paths ---
        paths = ttk.LabelFrame(root, text=" 安裝位置 ", padding=self.PAD)
        paths.pack(fill="x", pady=6)
        self.var_server = tk.StringVar(value=r"C:\mc-paper")
        self.var_backup = tk.StringVar(value=r"C:\mc-backup")
        self.var_toolkit = tk.StringVar(value=r"C:\mc-toolkit")
        for label, var in (("伺服器", self.var_server),
                           ("備份", self.var_backup),
                           ("工具", self.var_toolkit)):
            row = ttk.Frame(paths)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, width=8).pack(side="left")
            entry = ttk.Entry(row, textvariable=var)
            entry.pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="瀏覽…", width=8,
                       command=lambda v=var: self._pick(v)).pack(side="left",
                                                                 padx=(6, 0))
        ttk.Label(paths, foreground="#a06000", wraplength=self.px(740),
                  text="不要選在「文件」「圖片」「桌面」底下——受控資料夾存取會"
                       "無聲擋掉寫入，伺服器會莫名死掉且查不到原因。"
                  ).pack(anchor="w", pady=(6, 0))

        # --- server core ---
        core = ttk.LabelFrame(root, text=" 伺服器核心 ", padding=self.PAD)
        core.pack(fill="x", pady=6)
        self.var_paper = tk.BooleanVar(value=True)
        ttk.Checkbutton(core, text="下載 Paper", variable=self.var_paper,
                        command=self._toggle_paper).pack(anchor="w")
        row = ttk.Frame(core)
        row.pack(fill="x", pady=(4, 0))
        ttk.Label(row, text="版本", width=8).pack(side="left")
        self.combo_version = ttk.Combobox(row, state="readonly", width=18)
        self.combo_version.pack(side="left")
        ttk.Label(row, foreground="#666",
                  text="　已經有 paper.jar 的話取消勾選即可").pack(side="left")

        # --- options ---
        opts = ttk.LabelFrame(root, text=" 設定與自動化 ", padding=self.PAD)
        opts.pack(fill="x", pady=6)
        self.var_rcon = tk.BooleanVar(value=True)
        self.var_tasks = tk.BooleanVar(value=True)
        self.var_fw = tk.BooleanVar(value=True)
        self.var_shortcut = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, variable=self.var_rcon,
                        text="開啟 RCON（自動產生密碼寫入 server.properties）"
                        ).pack(anchor="w")
        ttk.Checkbutton(opts, variable=self.var_tasks,
                        text="註冊排程工作（備份、看門狗、內網控制台）"
                        ).pack(anchor="w")
        self.chk_fw = ttk.Checkbutton(
            opts, variable=self.var_fw,
            text="建立防火牆規則，讓區網其他裝置連得到控制台")
        self.chk_fw.pack(anchor="w")
        ttk.Checkbutton(opts, variable=self.var_shortcut,
                        text="在桌面建立捷徑").pack(anchor="w")

        row = ttk.Frame(opts)
        row.pack(fill="x", pady=(6, 0))
        ttk.Label(row, text="控制台埠", width=10).pack(side="left")
        self.var_port = tk.StringVar(value="8099")
        ttk.Entry(row, textvariable=self.var_port, width=8).pack(side="left")

        # --- action ---
        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=(10, 4))
        self.btn = ttk.Button(bar, text="開始安裝", command=self._start)
        self.btn.pack(side="left")
        self.progress = ttk.Progressbar(bar, mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True, padx=10)

        self.log = tk.Text(root, height=9, wrap="word",
                           font=("Consolas", 9), state="disabled")
        self.log.pack(fill="both", expand=True)

    def _pick(self, var):
        chosen = filedialog.askdirectory(initialdir=var.get() or "C:\\")
        if chosen:
            var.set(os.path.normpath(chosen))

    def _toggle_paper(self):
        self.combo_version.configure(
            state="readonly" if self.var_paper.get() else "disabled")

    # ------------------------------------------------------- worker plumbing
    def _post(self, kind, payload):
        self.q.put((kind, payload))

    def _drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.log.configure(state="normal")
                    self.log.insert("end", payload + "\n")
                    self.log.see("end")
                    self.log.configure(state="disabled")
                elif kind == "progress":
                    self.progress["value"] = payload
                elif kind == "env":
                    key, text, colour = payload
                    self.env_labels[key].configure(text=text, foreground=colour)
                elif kind == "versions":
                    self.combo_version["values"] = payload
                    if payload:
                        self.combo_version.current(0)
                elif kind == "done":
                    self.busy = False
                    self.btn.configure(state="normal", text="開始安裝")
                    (messagebox.showinfo if payload[0] else
                     messagebox.showerror)(APP_TITLE, payload[1])
        except queue.Empty:
            pass
        self.after(80, self._drain)

    def say(self, text):
        self._post("log", text)

    # ------------------------------------------------------------ env check
    def _check_environment(self):
        major, raw = java_version()
        if major is None:
            self._post("env", ("java", "找不到 Java —— 需要 21 以上", "#b00"))
        elif major < 21:
            self._post("env", ("java", "%s（太舊，Paper 需要 21 以上）" % raw,
                               "#b00"))
        else:
            self._post("env", ("java", "%s" % raw, "#070"))

        cfa = controlled_folder_access()
        if cfa is None:
            self._post("env", ("cfa", "查不到狀態", "#888"))
        elif cfa:
            self._post("env", ("cfa", "開啟中 —— 安裝路徑請避開文件/桌面",
                               "#a06000"))
        else:
            self._post("env", ("cfa", "未開啟", "#070"))

        if is_admin():
            self._post("env", ("admin", "有", "#070"))
        else:
            self._post("env", ("admin", "沒有 —— 無法建立防火牆規則", "#a06000"))
            self.after(0, lambda: (self.var_fw.set(False),
                                   self.chk_fw.configure(state="disabled")))

        try:
            self._post("versions", paper_versions()[:20])
        except Exception as exc:
            self.say("無法取得 Paper 版本清單：%s" % exc)
            self.after(0, lambda: self.var_paper.set(False))

    # -------------------------------------------------------------- install
    def _start(self):
        if self.busy:
            return
        server = os.path.normpath(self.var_server.get().strip())
        backup = os.path.normpath(self.var_backup.get().strip())
        toolkit = os.path.normpath(self.var_toolkit.get().strip())
        if not (server and backup and toolkit):
            messagebox.showerror(APP_TITLE, "三個路徑都要填。")
            return
        bad = [p for p in (server, backup, toolkit) if under_protected(p)]
        if bad and not messagebox.askyesno(
                APP_TITLE,
                "這些路徑在受保護的資料夾底下：\n\n%s\n\n"
                "受控資料夾存取會無聲擋掉寫入，伺服器很可能會莫名死掉。\n"
                "仍要繼續嗎？" % "\n".join(bad)):
            return
        try:
            port = int(self.var_port.get())
        except ValueError:
            messagebox.showerror(APP_TITLE, "控制台埠必須是數字。")
            return

        self.busy = True
        self.btn.configure(state="disabled", text="安裝中…")
        threading.Thread(target=self._install,
                         args=(server, backup, toolkit, port),
                         daemon=True).start()

    def _install(self, server, backup, toolkit, port):
        try:
            steps = [s for s, on in (
                ("copy", True),
                ("paper", self.var_paper.get()),
                ("rcon", self.var_rcon.get()),
                ("config", True),
                ("tasks", self.var_tasks.get()),
                ("firewall", self.var_fw.get()),
                ("shortcut", self.var_shortcut.get()),
            ) if on]
            done = 0

            def tick():
                nonlocal done
                done += 1
                self._post("progress", int(done / len(steps) * 100))

            for name in steps:
                getattr(self, "_step_" + name)(server, backup, toolkit, port)
                tick()

            self.say("")
            self.say("安裝完成。")
            self._post("done", (True,
                                "安裝完成。\n\n控制台： http://localhost:%d\n"
                                "權杖在 %s\\web-console.config.json"
                                % (port, toolkit)))
        except Exception as exc:
            self.say("")
            self.say("失敗：%s" % exc)
            self._post("done", (False, "安裝失敗：\n%s" % exc))

    # ---- steps ----------------------------------------------------------
    def _step_copy(self, server, backup, toolkit, port):
        self.say("複製工具到 %s …" % toolkit)
        src = bundle_dir()
        os.makedirs(toolkit, exist_ok=True)
        os.makedirs(backup, exist_ok=True)
        os.makedirs(server, exist_ok=True)
        for folder in ("scripts", "windows", "docs"):
            source = os.path.join(src, folder)
            if os.path.isdir(source):
                shutil.copytree(source, os.path.join(toolkit, folder),
                                dirs_exist_ok=True)
        for f in ("config.example.json", "README.md", "LICENSE",
                  "requirements.txt"):
            if os.path.exists(os.path.join(src, f)):
                shutil.copy2(os.path.join(src, f), os.path.join(toolkit, f))
        start_bat = os.path.join(toolkit, "windows", "start.bat")
        if os.path.exists(start_bat):
            shutil.copy2(start_bat, os.path.join(server, "start.bat"))
        self.say("  完成")

    def _step_paper(self, server, backup, toolkit, port):
        version = self.combo_version.get()
        if not version:
            self.say("沒有選版本，跳過 Paper 下載")
            return
        self.say("下載 Paper %s …" % version)
        url, name, build = paper_download(version)
        self.say("  build %s → %s" % (build, name))
        target = os.path.join(server, "paper.jar")
        with urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=120) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            got = 0
            with open(target, "wb") as fh:
                while True:
                    chunk = resp.read(262144)
                    if not chunk:
                        break
                    fh.write(chunk)
                    got += len(chunk)
                    if total:
                        self._post("progress", int(got / total * 100))
        self.say("  已存成 %s（%.1f MB）"
                 % (target, os.path.getsize(target) / 1048576))
        eula = os.path.join(server, "eula.txt")
        if not os.path.exists(eula):
            self.say("  注意：第一次啟動後要把 eula.txt 改成 eula=true")

    def _step_rcon(self, server, backup, toolkit, port):
        path = os.path.join(server, "server.properties")
        self.say("設定 RCON …")
        lines = []
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as fh:
                lines = fh.read().splitlines()
        wanted = {"enable-rcon": "true", "rcon.port": "25575"}
        existing = {}
        for line in lines:
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()
        if existing.get("rcon.password"):
            self.say("  已有密碼，保留不動")
        else:
            wanted["rcon.password"] = make_password()
            self.say("  已產生新密碼並寫入 server.properties")
        out, seen = [], set()
        for line in lines:
            key = line.split("=", 1)[0].strip() if "=" in line else None
            if key in wanted:
                out.append("%s=%s" % (key, wanted[key]))
                seen.add(key)
            else:
                out.append(line)
        for key, value in wanted.items():
            if key not in seen:
                out.append("%s=%s" % (key, value))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        self.say("  完成（伺服器需重新啟動才生效）")

    def _step_config(self, server, backup, toolkit, port):
        self.say("寫入 config.json …")
        path = os.path.join(toolkit, "config.json")
        cfg = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    cfg = json.load(fh)
                self.say("  已有設定檔，只更新路徑與埠")
            except ValueError:
                cfg = {}
        cfg.update({
            "serverDir": server,
            "backupDir": backup,
            "startBat": os.path.join(server, "start.bat"),
            "keepBackups": cfg.get("keepBackups", 7),
        })
        cfg.setdefault("java", {}).update(
            {"localPort": 25565, "port": 25565})
        cfg["java"].setdefault("host", "")
        cfg.setdefault("bedrock", {}).setdefault("host", "")
        cfg["bedrock"].setdefault("tunnelPort", 19132)
        cfg["bedrock"].setdefault("localPort", 19132)
        cfg.setdefault("mapUrl", "")
        cfg["webConsole"] = {"host": "0.0.0.0", "port": port}
        cfg.setdefault("discord", {"tokenFile": "", "authorizedUserIds": [],
                                   "rconUserIds": [], "logChannelId": ""})
        cfg.setdefault("cloudflare", {"projectName": "", "accountId": "",
                                      "tokenFile": "", "webDir": ""})
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=2, ensure_ascii=False)
        self.say("  完成（對外網域等欄位之後再填）")

    def _step_tasks(self, server, backup, toolkit, port):
        self.say("註冊排程工作 …")
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pyw):
            ok, out = run(["where", "pythonw"], timeout=30)
            pyw = out.strip().splitlines()[0] if ok and out.strip() else ""
        ps = os.path.join(toolkit, "windows")

        jobs = [
            ("MC Toolkit Backup", "Daily -At 04:00",
             "powershell.exe",
             '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File '
             '"%s"' % os.path.join(ps, "backup-world.ps1")),
            ("MC Toolkit Watchdog", "Once -At 00:00 "
             "-RepetitionInterval (New-TimeSpan -Minutes 5)",
             "powershell.exe",
             '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File '
             '"%s"' % os.path.join(ps, "watchdog.ps1")),
        ]
        if pyw:
            jobs.append(("MC Toolkit Web Console", "AtLogOn", pyw,
                         '"%s"' % os.path.join(toolkit, "scripts",
                                               "web-console.py")))
        else:
            self.say("  找不到 pythonw.exe，跳過控制台的排程")

        for name, trigger, exe, args in jobs:
            script = (
                '$a = New-ScheduledTaskAction -Execute "{exe}" '
                '-Argument \'{args}\' -WorkingDirectory "{wd}"; '
                '$t = New-ScheduledTaskTrigger -{trig}; '
                '$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries '
                '-DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew '
                '-ExecutionTimeLimit ([TimeSpan]::Zero); '
                '$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME '
                '-LogonType Interactive -RunLevel Limited; '
                'Register-ScheduledTask -TaskName "{name}" -InputObject '
                '(New-ScheduledTask -Action $a -Trigger $t -Settings $s '
                '-Principal $p) -Force | Out-Null'
            ).format(exe=exe, args=args, wd=toolkit, trig=trigger, name=name)
            ok, out = powershell(script)
            self.say("  %s %s" % ("✓" if ok else "✗", name))
            if not ok:
                self.say("     %s" % out.strip().splitlines()[0][:110]
                         if out.strip() else "")

    def _step_firewall(self, server, backup, toolkit, port):
        self.say("建立防火牆規則（TCP %d，限本地子網路）…" % port)
        script = (
            "$n='MC Toolkit Web Console (LAN)'; "
            "Get-NetFirewallRule -DisplayName $n -ErrorAction SilentlyContinue"
            " | Remove-NetFirewallRule -ErrorAction SilentlyContinue; "
            "New-NetFirewallRule -DisplayName $n -Direction Inbound "
            "-Protocol TCP -LocalPort %d -RemoteAddress LocalSubnet "
            "-Action Allow -Profile Private,Domain | Out-Null" % port)
        ok, out = powershell(script)
        if ok:
            self.say("  完成")
            prof = powershell("(Get-NetConnectionProfile).NetworkCategory")[1]
            if "Public" in prof:
                self.say("  注意：目前網路是「公用」，規則只在私人/網域生效。"
                         "請到 Windows 設定改成私人網路。")
        else:
            self.say("  失敗（需要系統管理員權限）：%s"
                     % out.strip().splitlines()[0][:110] if out.strip() else "")

    def _step_shortcut(self, server, backup, toolkit, port):
        self.say("建立桌面捷徑 …")
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        items = [
            ("啟動 Minecraft 伺服器.lnk", os.path.join(server, "start.bat"),
             server),
            ("Minecraft 控制台.lnk",
             os.path.join(toolkit, "windows", "web-console.bat"), toolkit),
        ]
        for name, target, workdir in items:
            if not os.path.exists(target):
                continue
            script = (
                "$s=(New-Object -ComObject WScript.Shell)"
                ".CreateShortcut('{lnk}'); $s.TargetPath='{tgt}'; "
                "$s.WorkingDirectory='{wd}'; $s.Save()"
            ).format(lnk=os.path.join(desktop, name), tgt=target, wd=workdir)
            ok, _ = powershell(script, timeout=60)
            self.say("  %s %s" % ("✓" if ok else "✗", name))


def probe():
    """Print what this display resolves to and exit.

    Support aid: DPI problems look identical from the outside ("everything is
    tiny") whatever the cause, and these four numbers separate them.
    """
    enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    dpi = root.winfo_fpixels("1i")
    print("DPI              %.1f" % dpi)
    print("scale            %.2fx" % (dpi / 96.0))
    print("tk scaling       %.3f" % (dpi / 72.0))
    print("screen           %d x %d"
          % (root.winfo_screenwidth(), root.winfo_screenheight()))
    print("window would be  %d x %d"
          % (min(int(860 * dpi / 96), int(root.winfo_screenwidth() * 0.92)),
             min(int(760 * dpi / 96), int(root.winfo_screenheight() * 0.88))))
    root.destroy()


if __name__ == "__main__":
    if "--probe" in sys.argv:
        probe()
    else:
        enable_dpi_awareness()
        Installer().mainloop()
