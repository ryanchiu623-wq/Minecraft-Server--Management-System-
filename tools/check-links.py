"""Check every relative markdown link and heading anchor in the repo."""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# The repository root, not this script's folder - walking tools/ alone finds
# nothing and reports a clean run, which is the worst possible failure for a
# checker.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def slug(text):
    s = text.lower()
    s = re.sub(r"[^\w\s一-鿿-]", "", s)
    return re.sub(r"\s+", "-", s.strip())


def anchors(path):
    out = set()
    for line in io.open(path, encoding="utf-8"):
        m = re.match(r"^#{1,6}\s+(.*?)\s*$", line)
        if m:
            out.add(slug(m.group(1)))
    return out


files = []
for base, dirs, names in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d not in (".git", "build", "dist",
                                            "__pycache__")]
    files += [os.path.join(base, n) for n in names if n.endswith(".md")]

bad = 0
checked = 0
for path in sorted(files):
    text = io.open(path, encoding="utf-8").read()
    links = [l for l in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text)
             if not l.startswith(("http", "mailto:"))]
    for link in links:
        if link.startswith("../../"):
            continue                      # GitHub repo-relative, not a file
        checked += 1
        file_part, _, anchor = link.partition("#")
        target = (os.path.normpath(os.path.join(os.path.dirname(path),
                                                file_part))
                  if file_part else path)
        rel = os.path.relpath(path, ROOT)
        if not os.path.exists(target):
            print("  BAD FILE   %-34s %s" % (rel, link))
            bad += 1
        elif anchor and anchor not in anchors(target):
            print("  BAD ANCHOR %-34s %s" % (rel, link))
            bad += 1

print()
print("checked %d links across %d files, %d broken" % (checked, len(files), bad))
