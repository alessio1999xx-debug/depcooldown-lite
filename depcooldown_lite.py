#!/usr/bin/env python3
"""depcooldown-lite: flag pinned PyPI/npm dependencies released too recently.

Reads one requirements.txt or package-lock.json, asks the public PyPI / npm
registry when each pinned version was published, and fails (exit 1) if any of
them is younger than the cooldown (default 7 days). Read-only, stdlib-only.

MIT License. Full version (lockfile diffing, safe-version suggestions, offline
cache, uv.lock / poetry.lock / pyproject.toml, Markdown CI summary):
https://py-forge.com/products/depcooldown-dependency-release-age-gate
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional, Tuple

__version__ = "0.1.0"

PYPI_URL = "https://pypi.org/pypi/{package}/json"
NPM_URL = "https://registry.npmjs.org/{package}"

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2


def parse_iso(ts: str) -> datetime.datetime:
    cleaned = ts.strip().replace("Z", "+00:00")
    cleaned = re.sub(r"(\.\d{6})\d+", r"\1", cleaned)
    try:
        dt = datetime.datetime.fromisoformat(cleaned)
    except ValueError:
        dt = datetime.datetime.strptime(cleaned[:19], "%Y-%m-%dT%H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def parse_requirements(content: str) -> Dict[str, str]:
    """Return {name: version} for strictly pinned name==version lines."""
    pinned: Dict[str, str] = {}
    for raw in content.splitlines():
        line = raw.split(" #", 1)[0].split(";", 1)[0].strip()
        if not line or line.startswith(("#", "-")):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]*\])?\s*==\s*([A-Za-z0-9_.\-+!]+)$", line)
        if m:
            pinned[m.group(1).lower().replace("_", "-")] = m.group(2)
    return pinned


def parse_package_lock(content: str) -> Dict[str, str]:
    """Return {name: version} from an npm package-lock.json (v1, v2 or v3)."""
    data = json.loads(content)
    pinned: Dict[str, str] = {}
    packages = data.get("packages")
    if isinstance(packages, dict):
        for path, meta in packages.items():
            if not path or not isinstance(meta, dict) or meta.get("link"):
                continue
            name = meta.get("name") or path.split("node_modules/")[-1]
            if meta.get("version"):
                pinned[name] = meta["version"]
    elif isinstance(data.get("dependencies"), dict):
        for name, meta in data["dependencies"].items():
            if isinstance(meta, dict) and meta.get("version"):
                pinned[name] = meta["version"]
    return pinned


def load_pins(path: str) -> Tuple[str, Dict[str, str]]:
    base = os.path.basename(path).lower()
    with open(path, "r", encoding="utf-8") as fh:
        content = fh.read()
    if base in ("package-lock.json", "npm-shrinkwrap.json"):
        return "npm", parse_package_lock(content)
    if base.endswith(".txt"):
        return "pypi", parse_requirements(content)
    raise ValueError(
        "depcooldown-lite reads requirements*.txt or package-lock.json only "
        "(uv.lock, poetry.lock and pyproject.toml are in the full DepCooldown)."
    )


def fetch_upload_time(ecosystem: str, package: str, version: str, timeout: float = 10.0) -> Optional[str]:
    """Return the ISO publish time of package==version, or None if unknown."""
    url = (NPM_URL if ecosystem == "npm" else PYPI_URL).format(package=urllib.parse.quote(package, safe="@"))
    req = urllib.request.Request(url, headers={"User-Agent": "depcooldown-lite/" + __version__, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as err:
        sys.stderr.write(f"warning: could not query {ecosystem} for {package}: {err}\n")
        return None
    if ecosystem == "npm":
        return (data.get("time") or {}).get(version)
    files = (data.get("releases") or {}).get(version) or []
    if files:
        return files[0].get("upload_time_iso_8601") or files[0].get("upload_time")
    return None


def audit(pins: Dict[str, str], ecosystem: str, cooldown_days: int, now: datetime.datetime,
          fetch: Callable[[str, str, str], Optional[str]]) -> List[dict]:
    results = []
    for name, ver in sorted(pins.items()):
        ts = fetch(ecosystem, name, ver)
        if ts is None:
            results.append({"package": name, "version": ver, "status": "UNVERIFIED", "age_days": None})
            continue
        age = (now - parse_iso(ts)).total_seconds() / 86400.0
        status = "FAIL" if age < cooldown_days else "OK"
        results.append({"package": name, "version": ver, "status": status, "age_days": round(age, 1)})
    return results


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="depcooldown_lite.py",
        description="Fail CI when a pinned PyPI/npm dependency was released fewer than N days ago.",
    )
    p.add_argument("file", help="requirements.txt or package-lock.json")
    p.add_argument("-c", "--cooldown", type=int, default=7, help="minimum release age in days (default 7)")
    p.add_argument("--json", action="store_true", help="print results as JSON")
    p.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return p


def main(argv: Optional[List[str]] = None, fetch=fetch_upload_time, now: Optional[datetime.datetime] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cooldown < 0:
        sys.stderr.write("error: --cooldown must be >= 0\n")
        return EXIT_USAGE
    try:
        ecosystem, pins = load_pins(args.file)
    except (OSError, ValueError) as err:
        sys.stderr.write(f"error: {err}\n")
        return EXIT_USAGE
    now = now or datetime.datetime.now(datetime.timezone.utc)
    results = audit(pins, ecosystem, args.cooldown, now, fetch)
    failed = [r for r in results if r["status"] == "FAIL"]
    if args.json:
        print(json.dumps({"file": args.file, "ecosystem": ecosystem, "cooldown_days": args.cooldown,
                          "results": results, "failed": len(failed)}, indent=2))
    else:
        print(f"{len(pins)} pinned {ecosystem} packages in {args.file}, cooldown {args.cooldown} days")
        for r in results:
            age = "unknown age" if r["age_days"] is None else f"{r['age_days']} days old"
            print(f"  {r['status']:<10} {r['package']}=={r['version']}  ({age})")
        print(f"{len(failed)} package(s) younger than {args.cooldown} days" if failed else "OK: nothing inside the cooldown")
    return EXIT_FAIL if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
