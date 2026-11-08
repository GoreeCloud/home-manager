#!/usr/bin/env python3
"""Read-only PyPI wheel metadata inventory for pinned Home Manager Core requirements.

No third-party package is downloaded, imported, installed or executed.
Classifications describe only the host Python/platform tags, not release safety,
the full dependency graph, or compatibility of arbitrary future platforms.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.specifiers import SpecifierSet
from pip._vendor.packaging.tags import Tag, sys_tags
from pip._vendor.packaging.utils import canonicalize_name, parse_wheel_filename

MAX_RESPONSE_BYTES = 2_000_000
MAX_PINNED_REQUIREMENTS = 200
MAX_WORKERS = 6
PYPI_URL = "https://pypi.org/pypi/{name}/{version}/json"
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def parse_direct_requirements(source: str) -> tuple[list[tuple[str, str]], list[str]]:
    """Only read the canonical constraint directive and declarative requirements."""
    pinned: list[tuple[str, str]] = []
    ranges: list[str] = []
    seen: set[str] = set()
    for line in source.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-"):
            if line != "-c homeassistant/package_constraints.txt":
                raise ValueError(f"unexpected requirements directive: {line}")
            continue
        requirement = Requirement(line)
        if requirement.marker or requirement.url or requirement.extras:
            raise ValueError(f"conditional, URL or extra direct requirement unsupported: {line}")
        name = canonicalize_name(requirement.name)
        if name in seen or not NAME_PATTERN.fullmatch(name):
            raise ValueError(f"duplicate or invalid package name: {name}")
        seen.add(name)
        specs = list(requirement.specifier)
        if len(specs) == 1 and specs[0].operator == "==" and "*" not in specs[0].version:
            pinned.append((name, specs[0].version))
        else:
            ranges.append(line)
    if not 20 <= len(pinned) <= MAX_PINNED_REQUIREMENTS:
        raise ValueError(f"unexpected pinned Core requirement count: {len(pinned)}")
    return pinned, ranges


def classify_release(
    name: str, version: str, release: dict[str, Any], tags: frozenset[Tag], python: str
) -> str:
    """Classify release artifacts from metadata; never download their content."""
    files = release.get("urls")
    if not isinstance(files, list):
        raise ValueError("PyPI release response has no file listing")
    saw_wheel = False
    saw_sdist = False
    for artifact in files:
        if not isinstance(artifact, dict):
            raise ValueError("invalid PyPI artifact metadata")
        filename = artifact.get("filename", "")
        if not isinstance(filename, str):
            raise ValueError("invalid PyPI artifact filename")
        if artifact.get("yanked"):
            continue
        if filename.endswith((".tar.gz", ".zip")):
            saw_sdist = True
        if not filename.endswith(".whl"):
            continue
        saw_wheel = True
        hashes = artifact.get("digests", {})
        if not isinstance(hashes, dict) or not SHA256_PATTERN.fullmatch(hashes.get("sha256", "")):
            raise ValueError("PyPI wheel metadata missing digest")
        wheel_name, wheel_version, _, wheel_tags = parse_wheel_filename(filename)
        if wheel_name != name or str(wheel_version) != version:
            raise ValueError("wheel filename disagrees with requested release")
        requires_python = artifact.get("requires_python")
        if requires_python and python not in SpecifierSet(requires_python):
            continue
        if wheel_tags.intersection(tags):
            return "compatible_wheel_metadata"
    if saw_wheel:
        return "no_matching_wheel"
    if saw_sdist:
        return "source_only"
    return "no_usable_files"


def fetch_release(name: str, version: str) -> dict[str, Any]:
    if not NAME_PATTERN.fullmatch(name) or not NAME_PATTERN.fullmatch(version):
        raise ValueError("invalid PyPI query parameters")
    url = PYPI_URL.format(name=quote(name, safe=""), version=quote(version, safe=""))
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "GoreeCloud-HomeManager-WheelMetadataAudit/1"})
    try:
        with urlopen(req, timeout=12) as response:
            if response.geturl() != url:
                raise ValueError("unexpected PyPI endpoint redirect")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        if exc.code == 404:
            return {"urls": []}
        raise
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("PyPI metadata response exceeds size limit")
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("urls"), list):
        raise ValueError("invalid PyPI release document")
    return data


def audit_pins(
    pinned: list[tuple[str, str]],
    *,
    fetcher: Any = fetch_release,
    tags: frozenset[Tag] | None = None,
    python: str = "3.14.10",
) -> list[dict[str, str]]:
    compatible = tags if tags is not None else frozenset(sys_tags())

    def one(item: tuple[str, str]) -> dict[str, str]:
        name, version = item
        try:
            result = classify_release(name, version, fetcher(name, version), compatible, python)
        except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError) as exc:
            # No exception content is printed: HTTP errors can contain URL data.
            result = "metadata_error_" + type(exc).__name__
        return {"name": name, "version": version, "status": result}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        return sorted(pool.map(one, pinned), key=lambda item: item["name"])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--requirements", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args(argv)
    if sys.version_info[:3] != (3, 14, 10) or sys.platform != "linux":
        print("AUDIT ERROR: requires the pinned Linux Python 3.14.10 host", file=sys.stderr)
        return 2
    try:
        pinned, ranges = parse_direct_requirements(args.requirements.read_text(encoding="utf-8"))
        results = audit_pins(pinned)
        report = {
            "scope": "direct exact Core pins only, PyPI JSON metadata, current Linux runner tags",
            "python": "3.14.10",
            "requirements": len(pinned),
            "unresolved_ranges": ranges,
            "results": results,
        }
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print("AUDIT ERROR: " + type(exc).__name__, file=sys.stderr)
        return 2
    unavailable = [item for item in results if item["status"] != "compatible_wheel_metadata"]
    errors = [item for item in unavailable if item["status"].startswith("metadata_error_")]
    print(f"METADATA INVENTORY: {len(pinned)} exact Core pins; "
          f"{len(pinned) - len(unavailable)} host-tagged wheel matches; "
          f"{len(unavailable)} unverified/unavailable; {len(ranges)} ranges not evaluated")
    for item in unavailable:
        print("WHEEL GAP: " + item["name"] + "==" + item["version"] + " " + item["status"])
    print("Scope: metadata only; no package downloads/install/import/execution or transitive solving")
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
