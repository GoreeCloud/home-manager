#!/usr/bin/env python3
"""Validate the exact pinned PyTurboJPEG 1.8.3 sdist without executing it.

Read-only source/provenance gate for a future disposable wheel build. No tar
members are extracted, no source code is run, no dependencies are installed.
"""

from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
from pathlib import PurePosixPath
import sys
import tarfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

PROJECT = "pyturbojpeg"
VERSION = "1.8.3"
FILENAME = "pyturbojpeg-1.8.3.tar.gz"
EXPECTED_SHA256 = "c131591a3990cc57f45a8b2705d6261c25df913a19b1fe88de5e911dbe04a1d4"
PYPI_JSON = "https://pypi.org/pypi/PyTurboJPEG/1.8.3/json"
MAX_METADATA_BYTES = 1_000_000
MAX_ARCHIVE_BYTES = 100_000
MAX_UNCOMPRESSED_BYTES = 800_000
MAX_FILES = 100

# Git blob SHA-1 from the reviewed upstream v1.8.3 tag. Comparing these values
# to individual tar member contents prevents executing a different setup.py.
SOURCE_BLOBS = {
    "setup.py": "bc7b242fe7c0df07a6c87ac6aa5e119594536032",
    "turbojpeg.py": "91f5e2eda2a0f4cc0ae482bc68cad668cb905ef0",
    "LICENSE": "658e3e016a19dab89842899dc50ebb4438753daa",
}


def git_blob_sha1(content: bytes) -> str:
    """Compute the same blob SHA-1 that GitHub uses for a file."""
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


def read_bounded(url: str, maximum: int) -> bytes:
    """Only retrieve public PyPI HTTPS bytes with strict final URL matching."""
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"pypi.org", "files.pythonhosted.org"}
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.port is not None
    ):
        raise ValueError("unapproved package metadata host or URL")
    req = Request(url, headers={"User-Agent": "GoreeCloud-HomeManager-PinnedSdistInspector/1"})
    with urlopen(req, timeout=15) as response:
        if response.geturl() != url:
            raise ValueError("unexpected external redirect")
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("package response exceeds the size bound")
    return data


def select_pinned_sdist(document: dict) -> str:
    """Select only the original exact PyPI sdist with its expected hash."""
    info = document.get("info", {})
    if not isinstance(info, dict):
        raise ValueError("PyPI metadata malformed")
    if info.get("version") != VERSION:
        raise ValueError("unexpected PyPI project version")
    files = document.get("urls")
    if not isinstance(files, list):
        raise ValueError("PyPI release has no files")
    candidates = [
        f for f in files
        if isinstance(f, dict)
        and f.get("filename") == FILENAME
        and f.get("packagetype") == "sdist"
        and not f.get("yanked")
        and f.get("digests", {}).get("sha256") == EXPECTED_SHA256
    ]
    if len(candidates) != 1:
        raise ValueError("exact PyPI source distribution/digest mismatch")
    url = candidates[0].get("url")
    if not isinstance(url, str) or urlsplit(url).hostname != "files.pythonhosted.org":
        raise ValueError("unexpected sdist file host")
    return url


def inspect_sdist(content: bytes, *, verify_digest: bool = True) -> list[str]:
    """Bounded TAR structure, file identity, MIT notice and inert source checks."""
    errors: list[str] = []
    if len(content) > MAX_ARCHIVE_BYTES:
        return ["source archive exceeds size bound"]
    if verify_digest and hashlib.sha256(content).hexdigest() != EXPECTED_SHA256:
        return ["pinned PyPI source archive SHA-256 mismatch"]
    prefix = FILENAME[:-7] + "/"
    members: dict[str, bytes] = {}
    try:
        with tarfile.open(fileobj=BytesIO(content), mode="r:gz") as archive:
            parts = archive.getmembers()
            if len(parts) > MAX_FILES or sum(m.size for m in parts) > MAX_UNCOMPRESSED_BYTES:
                return ["source archive exceeds uncompressed member limits"]
            names: set[str] = set()
            for member in parts:
                path = member.name
                segments = PurePosixPath(path).parts
                if (
                    not path.startswith(prefix)
                    or path.startswith("/")
                    or "\\" in path
                    or any(x in (".", "..") for x in segments)
                    or (not member.isfile() and not member.isdir())
                ):
                    errors.append("source archive has unsafe path or member type")
                    break
                if path in names:
                    errors.append("source archive has duplicate member names")
                    break
                names.add(path)
                if member.isfile() and path in {prefix + key for key in SOURCE_BLOBS}:
                    stream = archive.extractfile(member)
                    if stream is None:
                        errors.append("could not read required source file")
                        break
                    members[path.removeprefix(prefix)] = stream.read(member.size + 1)
    except (tarfile.TarError, OSError, ValueError) as exc:
        return ["source archive unreadable: " + type(exc).__name__]
    if errors:
        return errors
    for name, expected_blob in SOURCE_BLOBS.items():
        body = members.get(name)
        if body is None:
            errors.append("required upstream file missing: " + name)
        elif git_blob_sha1(body) != expected_blob:
            errors.append("upstream source/tag identity mismatch: " + name)
    license_body = members.get("LICENSE", b"")
    if not license_body.startswith(b"MIT License\n") or b"Copyright (c) 2018-2026 Lilo Huang" not in license_body:
        errors.append("upstream MIT license notice missing")
    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-archive", default=None, help="Optional predownloaded archive (offline CI tests)")
    args = p.parse_args(argv)
    try:
        if args.source_archive is None:
            meta = json.loads(read_bounded(PYPI_JSON, MAX_METADATA_BYTES))
            url = select_pinned_sdist(meta)
            body = read_bounded(url, MAX_ARCHIVE_BYTES)
        else:
            from pathlib import Path
            body = Path(args.source_archive).read_bytes()
        failures = inspect_sdist(body)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("SDIST FAIL: " + type(exc).__name__, file=sys.stderr)
        return 2
    for problem in failures:
        print("SDIST FAIL: " + problem, file=sys.stderr)
    if failures:
        return 1
    print("SDIST PASS: exact PyPI SHA-256, safe TAR, matching upstream setup.py/turbojpeg.py/MIT license")
    print("Scope: source inspection only; no extraction, dependency install, code execution, wheel build or runtime")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
