"""Fail when a pin in django/requirements-*.txt is missing from its lock file.

A txt edit committed without `make lock` would otherwise ship an image built
from stale pins (the Dockerfiles install the locks). Follows `-r` includes.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / "django"
PIN = re.compile(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*(==\s*\S+|@\s*\S+)$")


def pins(txt: pathlib.Path):
    seen, todo = set(), [txt]
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        for raw in path.read_text().splitlines():
            line = raw.split("#")[0].strip()
            if line.startswith("-r "):
                todo.append(path.parent / line[3:].strip())
            elif m := PIN.match(line):
                name = m.group(1).lower().replace("_", "-")
                yield path.name, name + m.group(2).replace(" ", "")


def main() -> int:
    bad = []
    for name in ("web", "worker"):
        lock = (ROOT / f"requirements-{name}.lock").read_text().lower().replace(" ", "")
        for source, pin in pins(ROOT / f"requirements-{name}.txt"):
            if pin.lower() not in lock:
                bad.append(f"{source} -> requirements-{name}.lock: {pin}")
    if bad:
        print("Lock drift (run `make lock`):\n  " + "\n  ".join(bad))
        return 1
    print("Lock files OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
