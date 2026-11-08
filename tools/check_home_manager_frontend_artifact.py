#!/usr/bin/env python3
"""Validate the exact pinned upstream frontend wheel without importing it.

A verified upstream artifact is not a GoreeCloud UI build, a software bill of
materials, or a security certification. Never extract or execute wheel members.
"""

from __future__ import annotations

import argparse
from email.parser import Parser
import hashlib
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from zipfile import BadZipFile, ZipFile

VERSION = "20261028.4"
FILENAME = f"home_assistant_frontend-{VERSION}-py3-none-any.whl"
EXPECTED_SHA256 = "e5e59b82e63b288323d35886272f2e490ee62f6c7aaa2c56e7ef45e300d44757"
MAX_WHEEL_BYTES = 150_000_000
MAX_UNCOMPRESSED_BYTES = 2_000_000_000
MAX_MEMBERS = 100_000
MAX_METADATA_BYTES = 1_000_000


def inspect(wheel: Path, *, verify_digest: bool = True) -> list[str]:
    """Perform bounded, read-only wheel structure and provenance checks."""
    if wheel.is_symlink() or not wheel.is_file() or wheel.name != FILENAME:
        return ["frontend wheel is missing, symlinked, or unexpectedly named"]
    if wheel.stat().st_size > MAX_WHEEL_BYTES:
        return ["frontend wheel exceeds the compressed size limit"]
    if verify_digest:
        sha256 = hashlib.sha256()
        with wheel.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                sha256.update(block)
        if sha256.hexdigest() != EXPECTED_SHA256:
            return ["frontend wheel SHA-256 differs from pinned PyPI artifact"]

    errors: list[str] = []
    prefix = f"home_assistant_frontend-{VERSION}.dist-info/"
    try:
        with ZipFile(wheel) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_MEMBERS:
                return ["frontend wheel exceeds ZIP entry count limit"]
            names = [item.filename for item in infos]
            if len(set(names)) != len(names):
                errors.append("frontend wheel contains duplicate ZIP paths")
            if sum(item.file_size for item in infos) > MAX_UNCOMPRESSED_BYTES:
                return ["frontend wheel exceeds uncompressed byte limit"]
            for item in infos:
                name = item.filename
                parts = PurePosixPath(name).parts
                if (
                    not name
                    or name.startswith("/")
                    or "\\" in name
                    or any(p in (".", "..") for p in parts)
                    or stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK
                    or item.flag_bits & 0x1
                ):
                    errors.append("frontend wheel has unsafe member paths or modes")
                    break

            metadata_name = prefix + "METADATA"
            license_name = prefix + "licenses/LICENSE.md"
            for required in (metadata_name, license_name, prefix + "WHEEL"):
                if required not in names:
                    errors.append("missing frontend metadata or Apache-2.0 license: " + required)
            if not any(name.startswith("hass_frontend/") for name in names):
                errors.append("frontend package asset directory is missing")
            if errors:
                return errors
            if any(zf.getinfo(p).file_size > MAX_METADATA_BYTES for p in (metadata_name, license_name)):
                return ["frontend metadata or license exceeds size limit"]
            metadata = Parser().parsestr(zf.read(metadata_name).decode("utf-8"))
            package = re.sub(r"[-_.]+", "-", metadata.get("Name", "")).lower()
            if package != "home-assistant-frontend":
                errors.append("frontend distribution name mismatch")
            if metadata.get("Version") != VERSION:
                errors.append("frontend distribution version mismatch")
            if metadata.get("License-Expression") != "Apache-2.0":
                errors.append("frontend license expression mismatch")
            if not zf.read(license_name).lstrip().startswith(b"Apache License"):
                errors.append("frontend license text missing")
            if not errors and zf.testzip() is not None:
                errors.append("frontend wheel failed ZIP checksum verification")
    except (BadZipFile, OSError, ValueError, UnicodeError, KeyError) as exc:
        return [f"frontend wheel invalid or unreadable: {type(exc).__name__}"]
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    path = args.wheel_dir / FILENAME
    failures = inspect(path)
    for failure in failures:
        print("FRONTEND FAIL: " + failure, file=sys.stderr)
    if failures:
        return 1
    print("FRONTEND PASS: upstream wheel name, SHA-256, metadata, license, ZIP and package assets")
    print("Scope: archive provenance only; no frontend imported, executed, rebranded or deployed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
