#!/usr/bin/env python3
"""Inspect a disposable PyTurboJPEG 1.8.3 wheel built from reviewed source.

No wheel code is imported, installed, executed, or published by this inspector.
"""

from __future__ import annotations

import argparse
from email.parser import Parser
from pathlib import Path, PurePosixPath
import stat
import sys
from zipfile import BadZipFile, ZipFile

import check_pyturbojpeg_sdist as source_guard

MAX_WHEEL_BYTES = 300_000
MAX_UNCOMPRESSED_BYTES = 700_000
MAX_MEMBERS = 80


def inspect(wheel: Path) -> list[str]:
    if (
        not wheel.is_file() or wheel.is_symlink()
        or wheel.name != "pyturbojpeg-1.8.3-py3-none-any.whl"
        or wheel.stat().st_size > MAX_WHEEL_BYTES
    ):
        return ["unexpected universal PyTurboJPEG wheel name or size"]
    errors: list[str] = []
    try:
        with ZipFile(wheel) as zf:
            entries = zf.infolist()
            names = [item.filename for item in entries]
            if len(entries) > MAX_MEMBERS or sum(item.file_size for item in entries) > MAX_UNCOMPRESSED_BYTES:
                return ["wheel entry count/size limit exceeded"]
            if len(set(names)) != len(names):
                return ["duplicate wheel member names"]
            for item in entries:
                name = item.filename
                if (
                    not name or name.startswith("/")
                    or "\\" in name
                    or ".." in PurePosixPath(name).parts
                    or stat.S_IFMT(item.external_attr >> 16) == stat.S_IFLNK
                    or item.flag_bits & 1
                ):
                    return ["unsafe wheel member path, type or encryption"]
            if any(name.lower().endswith((".so", ".pyd", ".dll", ".dylib")) for name in names):
                errors.append("wheel unexpectedly includes a native library")
            if "turbojpeg.py" not in names:
                errors.append("expected pure Python turbojpeg module missing")
            else:
                body = zf.read("turbojpeg.py")
                if source_guard.git_blob_sha1(body) != source_guard.SOURCE_BLOBS["turbojpeg.py"]:
                    errors.append("built module differs from inspected upstream tag")
            meta = [name for name in names if name.endswith(".dist-info/METADATA")]
            if len(meta) != 1:
                errors.append("distribution metadata missing or ambiguous")
            else:
                prefix = meta[0][:-len("METADATA")]
                metadata = Parser().parsestr(zf.read(meta[0]).decode("utf-8"))
                if metadata.get("Name", "").lower().replace("-", "").replace("_", "") != "pyturbojpeg":
                    errors.append("wheel project identity mismatch")
                if metadata.get("Version") != source_guard.VERSION:
                    errors.append("wheel version mismatch")
                if (metadata.get("License") or metadata.get("License-Expression")) != "MIT":
                    errors.append("wheel MIT license metadata missing")
                wheel_data = zf.read(prefix + "WHEEL").decode("utf-8") if prefix + "WHEEL" in names else ""
                if "Tag: py3-none-any" not in wheel_data:
                    errors.append("wheel is not the expected universal pure Python artifact")
                if prefix + "RECORD" not in names:
                    errors.append("wheel RECORD missing")
                licenses = [name for name in names if name.startswith(prefix + "licenses/") and name.endswith("LICENSE")]
                if len(licenses) != 1 or source_guard.git_blob_sha1(zf.read(licenses[0])) != source_guard.SOURCE_BLOBS["LICENSE"]:
                    errors.append("wheel MIT license text missing or different from verified source")
            if not errors and zf.testzip() is not None:
                errors.append("wheel ZIP CRC integrity failed")
    except (OSError, BadZipFile, KeyError, ValueError, UnicodeError) as exc:
        return ["wheel metadata unreadable: " + type(exc).__name__]
    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wheel-dir", type=Path, required=True)
    args = p.parse_args(argv)
    files = list(args.wheel_dir.glob("*.whl"))
    if len(files) != 1:
        print("WHEEL FAIL: expected exactly one local wheel", file=sys.stderr)
        return 2
    issues = inspect(files[0])
    for issue in issues:
        print("WHEEL FAIL: " + issue, file=sys.stderr)
    if issues:
        return 1
    print("PYTURBOJPEG WHEEL PASS: pure Python 1.8.3, upstream module+MIT license identity, universal tag")
    print("Scope: wheel build artifact only; not imported, installed, JPEG-decoded or released")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
