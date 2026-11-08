#!/usr/bin/env python3
"""Inert source and license preflight for the pinned, source-only PyRIC release.

The PyPI 0.1.6.3 source has no official wheel and no matching upstream Git
tag was independently established. This checker does NOT extract, import,
build, install or execute package code, and must not access wireless devices.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

VERSION = "0.1.6.3"
FILENAME = "PyRIC-0.1.6.3.tar.gz"
EXPECTED_SHA256 = "b539b01cafebd2406c00097f94525ea0f8ecd1dd92f7731f43eac0ef16c2ccc9"
PYPI_JSON = "https://pypi.org/pypi/PyRIC/0.1.6.3/json"
MAX_JSON_BYTES = 600_000
MAX_ARCHIVE_BYTES = 1_300_000
MAX_TOTAL_BYTES = 36_000_000
MAX_FILES = 2500
MAX_SOURCE_MEMBER = 350_000
REQUIRED_FILES = ("setup.py", "pyric/__init__.py", "LICENSE")
ROOT = "pyric-0.1.6.3"


def read_bounded(url: str, bound: int) -> bytes:
    """Get only exact, nonredirected public PyPI URLs with input caps."""
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname not in {"pypi.org", "files.pythonhosted.org"}
        or parts.username or parts.password or parts.query or parts.fragment or parts.port
    ):
        raise ValueError("unapproved PyPI endpoint")
    response = urlopen(Request(url, headers={"Accept": "application/json", "User-Agent": "GoreeCloud-PyRIC-SdistAudit/1"}), timeout=15)
    with response:
        if response.geturl() != url:
            raise ValueError("unexpected PyPI redirect")
        data = response.read(bound + 1)
    if len(data) > bound:
        raise ValueError("PyPI response exceeds strict size bound")
    return data


def select_release(metadata: dict) -> str:
    info = metadata.get("info")
    files = metadata.get("urls")
    if not isinstance(info, dict) or not isinstance(files, list) or info.get("version") != VERSION:
        raise ValueError("unexpected PyPI version or release metadata")
    matches = [
        item for item in files
        if isinstance(item, dict)
        and item.get("filename", "").lower() == FILENAME.lower()
        and item.get("packagetype") == "sdist"
        and not item.get("yanked")
        and isinstance(item.get("digests"), dict)
        and item["digests"].get("sha256") == EXPECTED_SHA256
    ]
    if len(matches) != 1:
        raise ValueError("pinned PyPI PyRIC sdist and SHA-256 mismatch")
    url = matches[0].get("url")
    if not isinstance(url, str) or urlsplit(url).hostname != "files.pythonhosted.org":
        raise ValueError("unapproved PyRIC source archive host")
    return url


def inspect_archive(data: bytes, *, check_hash: bool = True) -> dict[str, object]:
    if len(data) > MAX_ARCHIVE_BYTES:
        raise ValueError("PyRIC archive size cap exceeded")
    if check_hash and sha256(data).hexdigest() != EXPECTED_SHA256:
        raise ValueError("pinned PyPI source checksum mismatch")
    observed: dict[str, bytes] = {}
    names: set[str] = set()
    total = 0
    count = 0
    try:
        with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as archive:
            for member in archive:
                count += 1
                total += member.size
                if count > MAX_FILES or total > MAX_TOTAL_BYTES:
                    raise ValueError("TAR member or uncompressed bytes limit exceeded")
                name = member.name
                parts = PurePosixPath(name).parts
                if (
                    not parts
                    or parts[0].casefold() != ROOT
                    or name.startswith("/")
                    or "\\" in name
                    or ".." in parts
                    or (not member.isfile() and not member.isdir())
                ):
                    raise ValueError("unsafe source archive member path or type")
                if name in names:
                    raise ValueError("duplicate TAR member")
                names.add(name)
                relative = "/".join(parts[1:])
                if member.isfile() and relative in REQUIRED_FILES:
                    if member.size > MAX_SOURCE_MEMBER:
                        raise ValueError("required source member too large")
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ValueError("required source member unavailable")
                    content = stream.read(member.size + 1)
                    if len(content) != member.size:
                        raise ValueError("truncated source member")
                    observed[relative] = content
    except (tarfile.TarError, OSError) as exc:
        raise ValueError("unreadable PyRIC TAR") from exc
    if set(observed) != set(REQUIRED_FILES):
        raise ValueError("PyRIC setup, package init, or license is missing")
    setup = observed["setup.py"].decode("utf-8")
    package = observed["pyric/__init__.py"].decode("utf-8")
    license_text = observed["LICENSE"].decode("utf-8")
    if "GNU General Public License" not in license_text or "Dale" not in license_text:
        raise ValueError("source GPL attribution missing or unexpected")
    if "PyRIC" not in setup:
        raise ValueError("PyRIC setup declaration not found")
    return {
        "version": VERSION,
        "sha256": sha256(data).hexdigest(),
        "archive_members_checked": count,
        "source_only": True,
        "setup_imports_pyric": "import pyric" in setup,
        "GPL_source_notice": True,
        "matching_0_1_6_3_git_tag_verified": False,
        "source_executed": False,
        "device_accessed": False,
        "release_ready": False,
        "pyric_declares_version": "0.1.6.3" in package,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        url = select_release(json.loads(read_bounded(PYPI_JSON, MAX_JSON_BYTES)))
        result = inspect_archive(read_bounded(url, MAX_ARCHIVE_BYTES))
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (ValueError, OSError, UnicodeError, TypeError, json.JSONDecodeError) as exc:
        print("PYRIC SOURCE FAIL: " + type(exc).__name__, file=sys.stderr)
        return 2
    print(f"PYRIC SOURCE PREFLIGHT PASS: PyPI SHA-256 and {result['archive_members_checked']} inert members")
    print(f"GPL notice present; setup imports package: {result['setup_imports_pyric']}")
    print("RELEASE BLOCKED: no matching Git tag verified; no source execution, wheel build or device access")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
