#!/usr/bin/env python3
"""Stage ONLY source-matched PyTurboJPEG 1.8.3 files for a disposable wheel build.

The downloaded source archive is hash checked, checked against GitHub source
blob identity, and scanned for TAR traversal before staging four required files.
No archive member is extracted using tarfile.extractall. This script does not
install dependencies, build wheels or execute upstream module contents.
"""

from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import sys
import tarfile

import check_pyturbojpeg_sdist as source_guard

SOURCE_FILES = ("setup.py", "turbojpeg.py", "README.md", "LICENSE")
ROOT = source_guard.FILENAME[:-7] + "/"


def stage_verified_source(body: bytes, destination: Path) -> None:
    """Atomically establish a new private source directory and copy 4 files."""
    failures = source_guard.inspect_sdist(body)
    if failures:
        raise ValueError("pinned source provenance or structure rejected")
    if destination.exists() or not destination.parent.is_dir() or destination.parent.is_symlink():
        raise ValueError("source destination must be a new directory in an existing parent")
    data: dict[str, bytes] = {}
    with tarfile.open(fileobj=BytesIO(body), mode="r:gz") as archive:
        for name in SOURCE_FILES:
            member = archive.getmember(ROOT + name)
            if not member.isfile() or member.size > 200_000:
                raise ValueError("unexpected source file type or size")
            reader = archive.extractfile(member)
            if reader is None:
                raise ValueError("source TAR member is unreadable")
            content = reader.read(member.size + 1)
            if len(content) != member.size:
                raise ValueError("source file read did not match TAR size")
            data[name] = content
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, content in data.items():
        path = destination / name
        with path.open("xb") as file:
            file.write(content)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        manifest = source_guard.read_bounded(source_guard.PYPI_JSON, source_guard.MAX_METADATA_BYTES)
        import json
        url = source_guard.select_pinned_sdist(json.loads(manifest))
        content = source_guard.read_bounded(url, source_guard.MAX_ARCHIVE_BYTES)
        stage_verified_source(content, args.output_dir)
    except (OSError, ValueError, tarfile.TarError, KeyError) as exc:
        print("SOURCE PREP FAIL: " + type(exc).__name__, file=sys.stderr)
        return 2
    print("SOURCE PREP PASS: exact pinned and tag-matched 1.8.3 source staged, four files only")
    print("Scope: no third-party code execution; wheel build requires a separate reviewed step")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
