#!/usr/bin/env python3
"""Desktop console for the Minecraft server.

Monitoring and management in one window: server / tunnel / map / backup
status, plus start, stop, backup, render and arbitrary RCON commands.

Probing reuses the functions in check-server.py rather than reimplementing
the Minecraft and RakNet protocols a second time.

Run:  pythonw console-gui.py     (or double-click console.bat)
"""

import ctypes
import importlib.util
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

# When frozen by PyInstaller, __file__ points into a temp extraction folder
# and sys.executable is the .exe. The scripts we drive live next to the exe,
# so resolve the folder from the exe in that case.
if getattr(sys, "frozen", False):
    HERE = os.path.dirname(os.path.abspath(sys.executable))
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
MAP_URL = settings.get("mapUrl", default="")
BACKUP_DIR = settings.get("backupDir", default="")

def _load(name, filename):
    """Load a sibling script as a module. Reuses the tested probe and RCON
    code instead of reimplementing the protocols a second time."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


probe = _load("mcprobe", "check-server.py")
rconmod = _load("mcrcon", "rcon.py")

sys.path.insert(0, HERE)
import settings  # noqa: E402

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def enable_dpi_awareness():
    """Tell Windows we draw at real pixels.

    Without this the window is rendered at 96 dpi and then bitmap-stretched by
    the display scale - on a 2880x1800 screen at 253% that means everything is
    drawn 2.5x too small and blown up, which looks badly blurred.
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


# --------------------------------------------------------------- helpers
def run(cmd, timeout=120):
    """Run a child process from the server folder. cwd matters: anything
    under Documents is blocked by Controlled Folder Access."""
    try:
        p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                           timeout=timeout, creationflags=NO_WINDOW,
                           encoding="utf-8", errors="replace")
        return p.returncode == 0, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        return False, str(exc)


def rcon(*commands):
    # In-process: a frozen exe cannot call "python rcon.py".
    return rconmod.execute(list(commands))


def service_running(name="playitd"):
    ok, out = run(["sc", "query", name], timeout=20)
    return "RUNNING" in out


def latest_backup():
    try:
        files = [f for f in os.listdir(BACKUP_DIR) if f.startswith("world-") and f.endswith(".zip")]
        if not files:
            return None
        newest = max(files, key=lambda f: os.path.getmtime(os.path.join(BACKUP_DIR, f)))
        path = os.path.join(BACKUP_DIR, newest)
        return {"name": newest,
                "age_h": (time.time() - os.path.getmtime(path)) / 3600,
                "mb": os.path.getsize(path) / 1048576,
                "count": len(files)}
    except OSError:
        return None


def last_sync():
    path = os.path.join(HERE, "sync-map.log")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = [ln for ln in fh if "Deploy finished" in ln]
        if not lines:
            return None
        return (time.time() - os.path.getmtime(path)) / 3600
    except OSError:
        return None


def jvm_heap():
    """Committed / used MB for the running server, via jcmd."""
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq java.exe", "/FO", "CSV"],
                             capture_output=True, text=True, timeout=20,
                             creationflags=NO_WINDOW).stdout
        pids = [ln.split('","')[1] for ln in out.splitlines() if ln.startswith('"java.exe')]
        for pid in pids:
            r = subprocess.run(["jcmd", pid, "GC.heap_info"], capture_output=True,
                               text=True, timeout=20, creationflags=NO_WINDOW).stdout
            if "garbage-first heap" in r:
                committed = int(r.split("committed ")[1].split("K")[0]) / 1024
                used = int(r.split("used ")[1].split("K")[0]) / 1024
                return committed, used
    except Exception:
        pass
    return None, None


# --------------------------------------------------------------- the app
class Console(tk.Tk):
    POLL_FAST = 10        # seconds: local checks
    POLL_SLOW = 60        # seconds: outside view (a network round trip)

    def __init__(self):
        super().__init__()
        self.title("Minecraft 伺服器控制台")

        # Now that the process is DPI aware the window is measured in real
        # pixels, so both Tk's point scaling and our own sizes must follow the
        # display scale or the whole UI comes out tiny.
        dpi = self.winfo_fpixels("1i")
        scale = dpi / 96.0
        self.tk.call("tk", "scaling", dpi / 72.0)
        self.geometry(f"{int(880 * scale)}x{int(620 * scale)}")
        self.minsize(int(760 * scale), int(560 * scale))

        try:
            ttk.Style().theme_use("vista")
        except tk.TclError:
            pass

        self.q = queue.Queue()
        self.busy = False
        self._last_slow = 0
        self._outside = None
        # Lets an action or the refresh button wake the poller immediately
        # instead of leaving the display stale for up to POLL_FAST seconds.
        self._wake = threading.Event()

        self._build()
        self.after(200, self._drain)
        threading.Thread(target=self._poll_loop, daemon=True).start()

    # ---------------- layout
    def _build(self):
        pad = {"padx": 10, "pady": 6}

        head = ttk.Frame(self)
        head.pack(fill="x", **pad)
        ttk.Label(head, text="伺服器控制台", font=("Segoe UI", 15, "bold")).pack(side="left")
        self.clock = ttk.Label(head, text="", foreground="#666")
        self.clock.pack(side="right")

        # --- status cards
        cards = ttk.Frame(self)
        cards.pack(fill="x", **pad)
        self.cards = {}
        for i, (key, title) in enumerate([
            ("server", "伺服器"), ("tunnel", "隧道"), ("map", "網頁地圖"),
            ("backup", "備份"), ("memory", "記憶體"),
        ]):
            f = ttk.LabelFrame(cards, text=title)
            f.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            cards.columnconfigure(i, weight=1)
            dot = tk.Label(f, text="●", fg="#999", font=("Segoe UI", 14))
            dot.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=(2, 6))
            val = ttk.Label(f, text="檢查中…", font=("Segoe UI", 9))
            val.grid(row=0, column=1, sticky="w", pady=(2, 6))
            self.cards[key] = (dot, val)

        # --- detail + players
        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=False, **pad)

        det = ttk.LabelFrame(mid, text="詳細狀態")
        det.pack(side="left", fill="both", expand=True)
        self.detail = tk.Text(det, height=7, wrap="none", font=("Consolas", 9),
                              relief="flat", background="#f7f7f7")
        self.detail.pack(fill="both", expand=True, padx=6, pady=6)
        self.detail.configure(state="disabled")

        ply = ttk.LabelFrame(mid, text="線上玩家")
        ply.pack(side="left", fill="both", padx=(8, 0))
        self.players = tk.Listbox(ply, width=22, height=7, relief="flat",
                                  background="#f7f7f7", font=("Segoe UI", 9))
        self.players.pack(fill="both", expand=True, padx=6, pady=6)

        # --- actions
        act = ttk.LabelFrame(self, text="操作")
        act.pack(fill="x", **pad)
        row = ttk.Frame(act)
        row.pack(fill="x", padx=6, pady=6)
        self.buttons = {}
        for key, text, fn in [
            ("start", "啟動伺服器", self.do_start),
            ("stop", "關閉伺服器", self.do_stop),
            ("backup", "立即備份", self.do_backup),
            ("render", "渲染並上傳地圖", self.do_render),
            ("playit", "重啟隧道", self.do_playit),
            ("map", "開啟地圖", lambda: webbrowser.open(MAP_URL)),
            ("folder", "開啟資料夾", lambda: os.startfile(HERE)),
            ("refresh", "重新整理", self.do_refresh),
        ]:
            b = ttk.Button(row, text=text, command=fn)
            b.pack(side="left", padx=(0, 6))
            self.buttons[key] = b

        # --- rcon
        rc = ttk.LabelFrame(self, text="RCON 指令")
        rc.pack(fill="both", expand=True, **pad)
        entry_row = ttk.Frame(rc)
        entry_row.pack(fill="x", padx=6, pady=(6, 0))
        self.cmd = ttk.Entry(entry_row, font=("Consolas", 10))
        self.cmd.pack(side="left", fill="x", expand=True)
        self.cmd.bind("<Return>", lambda _e: self.do_rcon())
        ttk.Button(entry_row, text="送出", command=self.do_rcon).pack(side="left", padx=(6, 0))

        self.out = tk.Text(rc, height=8, wrap="word", font=("Consolas", 9),
                           relief="flat", background="#1e1e1e", foreground="#dcdcdc",
                           insertbackground="#dcdcdc")
        self.out.pack(fill="both", expand=True, padx=6, pady=6)
        self.out.configure(state="disabled")

        self.status = ttk.Label(self, text="就緒", relief="sunken", anchor="w")
        self.status.pack(fill="x", side="bottom")

    # ---------------- output helpers
    def log(self, text):
        self.out.configure(state="normal")
        self.out.insert("end", time.strftime("[%H:%M:%S] ") + text.rstrip() + "\n")
        self.out.see("end")
        self.out.configure(state="disabled")

    def set_card(self, key, colour, text):
        dot, val = self.cards[key]
        dot.configure(fg=colour)
        val.configure(text=text)

    def set_busy(self, busy, what=""):
        self.busy = busy
        for b in self.buttons.values():
            b.configure(state="disabled" if busy else "normal")
        self.status.configure(text=(what or "執行中…") if busy else "就緒")

    # ---------------- background work
    def _poll_loop(self):
        while True:
            try:
                self.q.put(("state", self._collect()))
            except Exception as exc:
                self.q.put(("log", f"輪詢失敗: {exc}"))
            self._wake.wait(timeout=self.POLL_FAST)
            self._wake.clear()

    def _collect(self):
        st = {}
        ok, detail, lat = probe.java_status("127.0.0.1", 25565)
        st["java"] = (ok, detail, lat)
        st["bedrock_local"] = probe.bedrock_status("127.0.0.1", 19132)
        st["playit"] = service_running()
        st["bedrock_tunnel"] = probe.bedrock_status(probe.BE_HOST, probe.BE_PORT) if st["playit"] else (False, "playit 未執行", None)
        st["backup"] = latest_backup()
        st["sync_h"] = last_sync()
        st["heap"] = jvm_heap()

        now = time.time()
        if now - self._last_slow > self.POLL_SLOW:
            self._last_slow = now
            self._outside = probe.external_view(probe.JAVA_HOST)
        st["outside"] = self._outside
        return st

    def _drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "state":
                    self._render(payload)
                elif kind == "log":
                    self.log(payload)
                elif kind == "done":
                    self.set_busy(False)
        except queue.Empty:
            pass
        self.clock.configure(text=time.strftime("%Y-%m-%d %H:%M:%S"))
        self.after(300, self._drain)

    # ---------------- rendering
    def _render(self, st):
        up, jdetail, jlat = st["java"]
        self.set_card("server", "#2e9e4f" if up else "#c62828",
                      jdetail if up else "未執行")

        if not st["playit"]:
            self.set_card("tunnel", "#c62828", "playit 未執行")
        elif not st["bedrock_tunnel"][0]:
            self.set_card("tunnel", "#e08b1f", "公開位址無回應")
        elif st["outside"] and st["outside"][0] is False:
            self.set_card("tunnel", "#e08b1f", "外部看不到 Java")
        else:
            self.set_card("tunnel", "#2e9e4f", "外部連得進來")

        h = st["sync_h"]
        if h is None:
            self.set_card("map", "#999", "無紀錄")
        else:
            self.set_card("map", "#2e9e4f" if h < 2 else "#e08b1f", f"{h:.1f} 小時前同步")

        b = st["backup"]
        if not b:
            self.set_card("backup", "#c62828", "沒有備份")
        else:
            self.set_card("backup", "#2e9e4f" if b["age_h"] < 36 else "#e08b1f",
                          f"{b['age_h']:.0f} 小時前 · {b['count']} 份")

        committed, used = st["heap"]
        if committed:
            self.set_card("memory", "#2e9e4f", f"{used:.0f} / {committed:.0f} MB")
        else:
            self.set_card("memory", "#999", "未執行")

        outside_ok = st["outside"][0] if st["outside"] else None
        outside_text = {True: "線上", False: "離線", None: "未查詢"}[outside_ok]

        outside_ok = st["outside"][0] if st["outside"] else None
        outside_text = {True: "線上", False: "離線", None: "未查詢"}[outside_ok]

        lines = [
            f"Java     127.0.0.1:25565   {jdetail}" + (f"   {jlat} ms" if jlat else ""),
            f"基岩     127.0.0.1:19132   {st['bedrock_local'][1]}",
            f"playit   服務              {'RUNNING' if st['playit'] else 'STOPPED'}",
            f"隧道     {probe.BE_HOST}:{probe.BE_PORT}   {st['bedrock_tunnel'][1]}",
            f"外部     {probe.JAVA_HOST}   {outside_text}",
        ]
        if b:
            lines.append(f"備份     {b['name']}   {b['mb']:.1f} MB")
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", "\n".join(lines))
        self.detail.configure(state="disabled")

        # The status ping already carries the player sample, so only fall back
        # to RCON when someone is actually online. Polling RCON every 10 s just
        # to learn "nobody is here" filled the server log with connect/
        # disconnect lines.
        self.players.delete(0, "end")
        names = []
        if up:
            online = 0
            try:
                online = int(jdetail.split()[1].split("/")[0])
            except (IndexError, ValueError):
                online = 0
            if online:
                ok2, out2 = rcon("list")
                if ok2 and ":" in out2:
                    tail = out2.rsplit(":", 1)[-1].strip()
                    names = [n.strip() for n in tail.split(",") if n.strip()]
        for n in names or (["（無人在線）"] if up else ["（伺服器未執行）"]):
            self.players.insert("end", n)

    # ---------------- actions
    def _task(self, what, fn):
        if self.busy:
            return
        self.set_busy(True, what)
        self.log(f"▶ {what}")

        def worker():
            try:
                msg = fn()
            except Exception as exc:
                msg = f"失敗: {exc}"
            self.q.put(("log", msg))
            self.q.put(("done", None))
            # State just changed - re-check now, including the outside view.
            self._last_slow = 0
            self._wake.set()

        threading.Thread(target=worker, daemon=True).start()

    def do_start(self):
        if probe.java_status("127.0.0.1", 25565)[0]:
            messagebox.showinfo("已在執行", "伺服器已經在執行中。")
            return

        def go():
            subprocess.Popen(["cmd", "/c", "start", "MC Server", "/min",
                              os.path.join(HERE, "start.bat"), "/nopause"],
                             cwd=HERE, creationflags=NO_WINDOW)
            for _ in range(40):
                time.sleep(3)
                if probe.java_status("127.0.0.1", 25565)[0]:
                    return "伺服器已啟動"
            return "兩分鐘內沒有起來，請看伺服器視窗"
        self._task("啟動伺服器", go)

    def do_stop(self):
        st = probe.java_status("127.0.0.1", 25565)
        if not st[0]:
            messagebox.showinfo("未執行", "伺服器本來就沒在跑。")
            return
        if not messagebox.askyesno("確認關閉", "會先存檔再關閉，線上玩家都會斷線。\n確定要關閉伺服器嗎？"):
            return
        self._task("關閉伺服器", lambda: rcon("save-all", "stop")[1].strip() or "已送出關機指令")

    def do_backup(self):
        self._task("備份世界", lambda: run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", os.path.join(HERE, "backup-world.ps1")], timeout=900)[1].strip().splitlines()[-1])

    def do_render(self):
        def go():
            rcon(*[f"bluemap update {m}" for m in ("overworld", "world", "world_the_end")])
            for _ in range(40):
                time.sleep(10)
                ok, out = rcon("bluemap")
                if ok and "render-threads are idle" in out:
                    break
            else:
                return "渲染超過 7 分鐘，先不上傳"
            ok, out = run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                           "-File", os.path.join(HERE, "sync-map.ps1")], timeout=900)
            return "地圖已渲染並上傳" if ok else f"上傳失敗: {out.strip().splitlines()[-1]}"
        self._task("渲染並上傳地圖", go)

    def do_playit(self):
        def go():
            run(["sc", "stop", "playitd"], timeout=30)
            time.sleep(3)
            run(["sc", "start", "playitd"], timeout=30)
            time.sleep(15)
            return "playit 已重啟" if service_running() else "playit 重啟後仍未執行"
        self._task("重啟隧道", go)

    def do_refresh(self):
        self._last_slow = 0          # include the outside view in this pass
        self._wake.set()
        self.status.configure(text="重新整理中…")

    def do_rcon(self):
        cmd = self.cmd.get().strip()
        if not cmd:
            return
        self.cmd.delete(0, "end")
        self._task(f"RCON: {cmd}", lambda: rcon(cmd)[1].strip() or "（伺服器沒有回傳文字）")


if __name__ == "__main__":
    enable_dpi_awareness()
    Console().mainloop()
