#!/usr/bin/env python3
"""Inspect a locally built Home Manager wheel without importing its code.

This checks only package metadata, entrypoints, licenses, wheel integrity and
relative member paths. It is not a package execution or vulnerability audit.
"""

from __future__ import annotations

import argparse
import configparser
from email.parser import Parser
import hashlib
from pathlib import Path, PurePosixPath
import sys
from zipfile import BadZipFile, ZipFile

PACKAGE = "homeassistant"
VERSION = "2026.11.0"
ENTRY = "homeassistant.__main__:main"
MAX_METADATA_SIZE = 1_000_000
MAX_UNCOMPRESSED_SIZE = 300_000_000


def inspect(wheel: Path) -> list[str]:
    errors: list[str] = []
    if wheel.is_symlink() or not wheel.is_file() or wheel.suffix != ".whl":
        return ["wheel must be a regular .whl file"]
    try:
        with ZipFile(wheel) as archive:
            members = archive.infolist()
            paths = [m.filename for m in members]
            if len(set(paths)) != len(paths):
                errors.append("archive contains duplicate member names")
            for name in paths:
                parts = PurePosixPath(name).parts
                if (
                    not name
                    or name.startswith("/")
                    or "\\" in name
                    or any(part in ("..", ".") for part in parts)
                ):
                    errors.append("archive has an unsafe member path")
                    break
            if sum(m.file_size for m in members) > MAX_UNCOMPRESSED_SIZE:
                errors.append("archive exceeds uncompressed-size limit")
                return errors
            prefix = f"{PACKAGE}-{VERSION}.dist-info/"
            required = (
                prefix + "METADATA",
                prefix + "entry_points.txt",
                prefix + "licenses/LICENSE.md",
                "homeassistant/__main__.py",
            )
            for name in required:
                if name not in paths:
                    errors.append(f"missing wheel member: {name}")
            if errors:
                return errors
            for name in required[:3]:
                if archive.getinfo(name).file_size > MAX_METADATA_SIZE:
                    errors.append(f"metadata file exceeds size bound: {name}")
                    return errors
            raw_metadata = archive.read(prefix + "METADATA").decode("utf-8")
            metadata = Parser().parsestr(raw_metadata)
            if metadata.get("Name", "").lower() != PACKAGE:
                errors.append("unexpected wheel package name")
            if metadata.get("Version") != VERSION:
                errors.append("unexpected wheel version")
            if metadata.get("License-Expression") != "Apache-2.0":
                errors.append("Apache-2.0 license metadata missing")
            if not archive.read(prefix + "licenses/LICENSE.md").startswith(
                b"                                 Apache License"
            ):
                errors.append("wheel license text mismatch")
            entries = configparser.ConfigParser(interpolation=None)
            entries.read_string(archive.read(prefix + "entry_points.txt").decode("utf-8"))
            scripts = entries["console_scripts"] if entries.has_section("console_scripts") else {}
            if scripts.get("hass") != ENTRY or scripts.get("goreecloud-home-manager") != ENTRY:
                errors.append("branded CLI alias does not match hass entrypoint")
            if not errors and archive.testzip() is not None:
                errors.append("wheel archive failed CRC integrity check")
    except (OSError, BadZipFile, UnicodeError, ValueError, KeyError, configparser.Error) as exc:
        errors.append(f"could not validate wheel metadata: {type(exc).__name__}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        directory = args.wheel_dir.resolve(strict=True)
        if not directory.is_dir():
            raise ValueError("wheel directory is not a directory")
        candidates = sorted(directory.glob("homeassistant-*.whl"))
        if len(candidates) != 1:
            raise ValueError(f"expected exactly one Home Assistant wheel, found {len(candidates)}")
    except (OSError, ValueError) as exc:
        print(f"WHEEL FAIL: {exc}", file=sys.stderr)
        return 2
    problems = inspect(candidates[0])
    for problem in problems:
        print(f"WHEEL FAIL: {problem}", file=sys.stderr)
    if problems:
        return 1
    digest = hashlib.sha256()
    with candidates[0].open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    print(f"WHEEL PASS: package={PACKAGE} version={VERSION} aliases=2")
    print(f"WHEEL_SHA256={digest.hexdigest()}")
    print("Scope: archive+metadata only; package was not installed or executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
