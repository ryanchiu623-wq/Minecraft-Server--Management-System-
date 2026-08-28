#!/usr/bin/env python3
"""Build the desktop console into MC-Console.exe.

    python installer/build_console.py

Produces MC-Console.exe at the repository root. Unlike the installer, this one
bundles nothing: it loads check-server.py, rcon.py and settings.py from disk at
run time, so it always drives the same code the scheduled tasks do rather than
a copy frozen at build time. That is why it must stay beside the checkout - it
looks for scripts/ next to itself, and reads config.json from there.

Requires PyInstaller:  pip install pyinstaller
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAME = "MC-Console"


def main():
    if os.name != "nt":
        raise SystemExit("這個工具只能在 Windows 上建置。")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise SystemExit("缺少 PyInstaller，請先執行：pip install pyinstaller")

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        # A GUI: a console window behind it looks like something crashed.
        "--windowed",
        "--name", NAME,
        "--distpath", ROOT,
        "--workpath", os.path.join(ROOT, "build"),
        "--specpath", os.path.join(ROOT, "build"),
        os.path.join(ROOT, "scripts", "console-gui.py"),
    ]

    print("building %s.exe …" % NAME)
    if subprocess.run(args, cwd=ROOT).returncode != 0:
        raise SystemExit("建置失敗")

    exe = os.path.join(ROOT, NAME + ".exe")
    print()
    print("完成： %s" % exe)
    print("大小： %.1f MB" % (os.path.getsize(exe) / 1048576))
    print()
    print("這支 exe 必須留在 %s，" % ROOT)
    print("它會從旁邊的 scripts\\ 讀取腳本與 config.json。")

    shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)


if __name__ == "__main__":
    main()
