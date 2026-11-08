#!/usr/bin/env python3
"""Inert provenance gate for the scoped GC UI Foundations 1.0.1 release asset.

This does not install npm packages, run scripts, compile TypeScript, inject
styles into Home Assistant, or assert that a branded frontend exists.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile

PACKAGE = "@goreecloud/gc-ui"
VERSION = "1.0.1"
ASSET = "goreecloud-gc-ui-1.0.1.tgz"
EXPECTED_SHA256 = "275d7e6dc9503b2e74b3190bcecf176d73d2345860e8a20fa5faa3b326cd2298"
SOURCE_SHA = "7e0b61ee70af2edb87aa736cca483425f0aacaf4"
MAX_ARCHIVE_BYTES = 60_000
MAX_TOTAL_BYTES = 420_000
MAX_MEMBERS = 90
MAX_MEMBER_BYTES = 100_000


def inspect_tgz(blob: bytes, *, verify_sha: bool = True) -> dict[str, object]:
    if not blob or len(blob) > MAX_ARCHIVE_BYTES:
        raise ValueError("untrusted GC UI archive exceeds size bounds")
    digest = sha256(blob).hexdigest()
    if verify_sha and digest != EXPECTED_SHA256:
        raise ValueError("GC UI release tarball official SHA-256 mismatch")

    metadata: dict[str, bytes] = {}
    members_seen: set[str] = set()
    total = 0
    try:
        with tarfile.open(fileobj=BytesIO(blob), mode="r:gz") as archive:
            for member in archive:
                name = member.name
                normalized = PurePosixPath(name)
                parts = normalized.parts
                if (
                    name.startswith("/")
                    or "\\" in name or ".." in parts or "." in parts
                    or not parts or parts[0] != "package"
                    or (not member.isfile() and not member.isdir())
                ):
                    raise ValueError("unsafe GC UI package member path or type")
                if name in members_seen:
                    raise ValueError("duplicate GC UI package archive member")
                members_seen.add(name)
                total += member.size
                if len(members_seen) > MAX_MEMBERS or total > MAX_TOTAL_BYTES:
                    raise ValueError("GC UI package decompression bounds exceeded")
                if member.isfile() and member.size > MAX_MEMBER_BYTES:
                    raise ValueError("GC UI oversized package member")
                if member.isfile() and name in {"package/package.json", "package/LICENSE", "package/LICENSE.md"}:
                    fd = archive.extractfile(member)
                    if fd is None:
                        raise ValueError("missing GC UI metadata body")
                    body = fd.read(member.size + 1)
                    if len(body) != member.size:
                        raise ValueError("truncated GC UI package member")
                    metadata[name] = body
    except (tarfile.TarError, OSError) as exc:
        raise ValueError("GC UI release asset cannot be read") from exc

    if "package/package.json" not in metadata:
        raise ValueError("GC UI release package manifest missing")
    try:
        manifest = json.loads(metadata["package/package.json"])
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("GC UI release manifest is malformed") from exc
    if not isinstance(manifest, dict):
        raise ValueError("GC UI release manifest not an object")
    if manifest.get("name") != PACKAGE or manifest.get("version") != VERSION:
        raise ValueError("GC UI release name or supported version mismatched")
    if manifest.get("license") not in {"Apache-2.0", "Apache 2.0"}:
        raise ValueError("GC UI release Apache-2.0 license metadata missing")
    if manifest.get("private") is True:
        raise ValueError("GC UI published release archive unexpectedly private")
    for field in ("dependencies", "optionalDependencies", "peerDependencies"):
        if manifest.get(field) not in (None, {}):
            raise ValueError("GC UI stable foundations has unexpected runtime dependencies")
    exports = manifest.get("exports")
    if not isinstance(exports, dict) or not {".", "./tokens", "./css/tokens"}.issubset(exports):
        raise ValueError("GC UI stable package public exports are missing")
    license_text = metadata.get("package/LICENSE", metadata.get("package/LICENSE.md", b""))
    if b"Apache License" not in license_text or b"Version 2.0, January 2004" not in license_text:
        raise ValueError("GC UI Apache-2.0 license text missing")
    if not any(name.endswith(".css") for name in members_seen):
        raise ValueError("GC UI stable token stylesheet missing")
    if not any(name.endswith(".json") and name != "package/package.json" for name in members_seen):
        raise ValueError("GC UI stable tokens JSON missing")

    return {
        "asset_sha256": digest,
        "source_git_sha_in_release": SOURCE_SHA,
        "name": PACKAGE,
        "version": VERSION,
        "members_inspected": len(members_seen),
        "scope": "Foundations-only tokens, theme and color engine artifact identity",
        "dependencies_declared": False,
        "third_party_code_executed": False,
        "frontend_runtime_built": False,
        "goreecloud_ui_adopted": False,
        "release_ready": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        source = args.archive
        if (
            source.is_symlink() or not source.is_file()
            or source.name != ASSET or source.stat().st_size > MAX_ARCHIVE_BYTES
        ):
            raise ValueError("expected bounded original GC UI release archive")
        result = inspect_tgz(source.read_bytes())
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, UnicodeError) as exc:
        print("GC UI FOUNDATIONS FAIL: " + type(exc).__name__, file=sys.stderr)
        return 2
    print(f"GC UI FOUNDATIONS PASS: exact official 1.0.1 hash, {result['members_inspected']} inert members")
    print("Scope: stable foundations artifact only; no npm install, Home Assistant frontend or GC UI runtime acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
