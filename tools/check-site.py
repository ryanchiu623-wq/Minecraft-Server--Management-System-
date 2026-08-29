"""Structural checks for the project pages under docs/.

Catches the things that are invisible until someone opens the page in the
wrong theme or with a keyboard: unclosed tags, a colour defined only inside
the dark-mode block, a var() with no definition, a dead relative link.
"""
import io
import os
import re
import sys
from html.parser import HTMLParser

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "source", "track", "wbr"}


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append("line %d: stray </%s>" % (self.getpos()[0], tag))
        elif self.stack[-1][0] != tag:
            self.errors.append("line %d: </%s> does not close <%s> opened on %d"
                               % (self.getpos()[0], tag, self.stack[-1][0],
                                  self.stack[-1][1]))
            self.stack.pop()
        else:
            self.stack.pop()


def check(path):
    name = os.path.relpath(path, ROOT)
    html = io.open(path, encoding="utf-8").read()
    problems = 0

    t = Tags()
    t.feed(html)
    for e in t.errors + ["unclosed <%s> on line %d" % (n, l)
                         for n, l in t.stack]:
        print("  %-22s %s" % (name, e))
        problems += 1

    base = re.search(r":root\s*\{(.*?)\}", html, re.S)
    dark = re.search(
        r"@media \(prefers-color-scheme: dark\)\s*\{\s*:root[^{]*\{(.*?)\}",
        html, re.S)
    if base:
        declared = set(re.findall(r"(--[\w-]+)\s*:", base.group(1)))
        if dark:
            only_dark = set(re.findall(r"(--[\w-]+)\s*:",
                                       dark.group(1))) - declared
            for v in sorted(only_dark):
                print("  %-22s %s is defined only in dark mode" % (name, v))
                problems += 1
        for v in sorted(set(re.findall(r"var\((--[\w-]+)", html)) - declared):
            print("  %-22s %s is used but never defined" % (name, v))
            problems += 1

    for href in re.findall(r'href="([^"]+)"', html):
        if href.startswith(("http", "#", "mailto:")):
            continue
        if not os.path.exists(os.path.join(os.path.dirname(path),
                                           href.split("#")[0])):
            print("  %-22s dead link: %s" % (name, href))
            problems += 1

    for need, label in (("<title>", "no <title>"),
                        ('name="description"', "no meta description"),
                        ("background: var(--ground)", "body has no explicit "
                                                      "background"),
                        ("prefers-reduced-motion", "motion is not gated")):
        if need not in html:
            print("  %-22s %s" % (name, label))
            problems += 1

    print("  %-22s %s  (%.1f KB)"
          % (name, "clean" if not problems else "%d problem(s)" % problems,
             len(html.encode()) / 1024))
    return problems


pages = sorted(os.path.join(DOCS, f) for f in os.listdir(DOCS)
               if f.endswith(".html"))
total = sum(check(p) for p in pages)
print()
print("%d page(s), %d problem(s)" % (len(pages), total))
