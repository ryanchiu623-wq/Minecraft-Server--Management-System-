#!/usr/bin/env python3
"""The account for the web console's public entrance.

One username and a salted PBKDF2 hash live in web-console.config.json next to
the control token, so the password itself is never stored. web-console.py
checks a login against them; discord-control.py's /console-password and this
script's command line set them.

Usage (at the computer):
    python console_auth.py            set the username and password (asks)
    python console_auth.py --show     show which username is set
"""

import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "web-console.config.json")

ITERATIONS = 600_000      # OWASP's current PBKDF2-SHA256 recommendation
MIN_PASSWORD = 10
USERNAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")


def _read():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _write(cfg):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)


def _hash(password, salt, iterations):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                               bytes.fromhex(salt), iterations).hex()


def check_new(username, password):
    """The problem with a new username/password, or None if it is fine."""
    if not username or len(username) > 32 or not set(username) <= USERNAME_CHARS:
        return "帳號只能用英文字母、數字和 _ . -，最多 32 個字"
    if len(password) < MIN_PASSWORD:
        return "密碼至少要 %d 個字" % MIN_PASSWORD
    if password.lower() == username.lower():
        return "密碼不能和帳號一樣"
    return None


def set_login(username, password):
    problem = check_new(username, password)
    if problem:
        raise ValueError(problem)
    salt = secrets.token_hex(16)
    cfg = _read()
    cfg["login"] = {"user": username, "salt": salt, "iterations": ITERATIONS,
                    "hash": _hash(password, salt, ITERATIONS),
                    "set": time.strftime("%Y-%m-%d %H:%M:%S")}
    _write(cfg)


def configured_user():
    return (_read().get("login") or {}).get("user")


def verify(username, password):
    """Read fresh on every call, so a password changed from Discord applies
    to the running console straight away."""
    login = _read().get("login") or {}
    if not login.get("hash"):
        # Spend the same time as a real check so the answer leaks nothing.
        _hash(password or "", "00" * 16, ITERATIONS)
        return False
    good_user = hmac.compare_digest(str(username).lower(), login["user"].lower())
    digest = _hash(password or "", login["salt"], int(login.get("iterations", ITERATIONS)))
    return hmac.compare_digest(digest, login["hash"]) and good_user


def main():
    if "--show" in sys.argv:
        user = configured_user()
        print("目前的帳號：%s" % user if user else "還沒有設定帳號密碼")
        return 0
    username = input("帳號：").strip()
    password = getpass.getpass("密碼（不會顯示）：")
    again = getpass.getpass("再輸入一次：")
    if password != again:
        print("兩次密碼不一樣，沒有變更")
        return 1
    try:
        set_login(username, password)
    except ValueError as exc:
        print(exc)
        return 1
    print("已設定帳號 %s。網頁控制台不用重開就會生效。" % username)
    return 0


if __name__ == "__main__":
    sys.exit(main())
