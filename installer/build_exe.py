#!/usr/bin/env python3
"""Build the installer into a single .exe.

    python installer/build_exe.py

Produces dist/MinecraftToolkitSetup.exe - self-contained, so a user downloads
one file and runs it. scripts/, windows/ and docs/ are bundled as data and
unpacked to the install directory at run time.

Requires PyInstaller:  pip install pyinstaller
"""

import datetime
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAME = "MinecraftToolkitSetup"

# Payload folders shipped inside the exe. The separator is ; on Windows.
DATA = ["scripts", "windows", "docs", "bundled"]
FILES = ["config.example.json", "README.md", "LICENSE", "requirements.txt"]


def write_build_info():
    """Record which commit this build came from.

    An installer that cannot say what version it is makes a stale release
    invisible - the exe on the releases page looks identical to a current one.
    """
    def git(*args):
        try:
            out = subprocess.run(["git"] + list(args), cwd=ROOT,
                                 capture_output=True, text=True, timeout=30)
            return out.stdout.strip() if out.returncode == 0 else ""
        except Exception:
            return ""

    info = {
        "commit": git("rev-parse", "--short", "HEAD") or "unknown",
        "built": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "dirty": bool(git("status", "--porcelain")),
    }
    path = os.path.join(HERE, "build_info.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=2)
    return path, info


def main():
    if os.name != "nt":
        raise SystemExit("這個安裝程式只能在 Windows 上建置。")

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise SystemExit("缺少 PyInstaller，請先執行：pip install pyinstaller")

    info_path, info = write_build_info()
    print("building from %s%s"
          % (info["commit"], "  (未提交的變更)" if info["dirty"] else ""))

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        # No console window: this is a GUI installer, and a stray black window
        # behind it looks broken.
        "--windowed",
        # Ask for elevation up front. The firewall rule needs it, and being
        # refused halfway through an install is worse than being asked first.
        "--uac-admin",
        "--name", NAME,
        "--distpath", os.path.join(ROOT, "dist"),
        "--workpath", os.path.join(ROOT, "build"),
        "--specpath", os.path.join(ROOT, "build"),
    ]

    for folder in DATA:
        source = os.path.join(ROOT, folder)
        if os.path.isdir(source):
            args += ["--add-data", "%s;%s" % (source, folder)]
    for name in FILES:
        source = os.path.join(ROOT, name)
        if os.path.exists(source):
            args += ["--add-data", "%s;." % source]
    args += ["--add-data", "%s;." % info_path]

    icon = os.path.join(HERE, "icon.ico")
    if os.path.exists(icon):
        args += ["--icon", icon]

    args.append(os.path.join(HERE, "install-gui.py"))

    print("building %s.exe …" % NAME)
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit("建置失敗（PyInstaller 回傳 %d）" % result.returncode)

    exe = os.path.join(ROOT, "dist", NAME + ".exe")
    print()
    print("完成： %s" % exe)
    print("大小： %.1f MB" % (os.path.getsize(exe) / 1048576))

    # The intermediate build tree is large and reproducible; leave only dist/.
    shutil.rmtree(os.path.join(ROOT, "build"), ignore_errors=True)


if __name__ == "__main__":
    main()
