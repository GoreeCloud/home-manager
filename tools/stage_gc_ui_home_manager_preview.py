#!/usr/bin/env python3
"""Stage four source files from a SHA-verified GC UI Foundations 1.0.1 tgz.

Use only for the explicit synthetic Home Manager UI preview. This does not
call npm install, run a package script, change Home Assistant integrations,
or publish any artifact. Tar entries are inspected, never extractall'd.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys
import tarfile

from check_gc_ui_foundations_asset import inspect_tgz

FILES = {
    "package/src/index.mjs": "src/index.mjs",
    "package/src/gc-color-engine.mjs": "src/gc-color-engine.mjs",
    "package/src/gc-theme-runtime.mjs": "src/gc-theme-runtime.mjs",
    "package/styles/gc.v1.generated.css": "styles/gc.v1.generated.css",
}
MANIFEST = "package/provenance.json"


def stage_foundations(blob: bytes, destination: Path, *, verify_sha: bool = True) -> dict[str, object]:
    evidence = inspect_tgz(blob, verify_sha=verify_sha)
    if (
        destination.exists() or destination.is_symlink()
        or not destination.parent.is_dir() or destination.parent.is_symlink()
    ):
        raise ValueError("preview vendor destination must be new in a normal directory")
    selected: dict[str, bytes] = {}
    with tarfile.open(fileobj=BytesIO(blob), mode="r:gz") as archive:
        for path in [*FILES, MANIFEST]:
            entry=archive.getmember(path)
            if not entry.isfile() or entry.size>100_000:
                raise ValueError("expected bounded regular file is missing from foundations")
            reader=archive.extractfile(entry)
            if reader is None:
                raise ValueError("unreadable release asset member")
            body=reader.read(entry.size+1)
            if len(body)!=entry.size:
                raise ValueError("truncated GC UI source member")
            selected[path]=body
    try:
        provenance=json.loads(selected[MANIFEST])
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid source provenance manifest") from exc
    if (
        not isinstance(provenance,dict)
        or provenance.get("sourceRepository")!="GoreeCloud/gc-ui"
        or provenance.get("releaseVersion")!="1.0.1"
        or not isinstance(provenance.get("files"),dict)
    ):
        raise ValueError("upstream release provenance source or version mismatch")
    for path,body in selected.items():
        if path==MANIFEST:
            continue
        original=path.removeprefix("package/")
        if provenance["files"].get(original)!=sha256(body).hexdigest():
            raise ValueError("staged GC UI source digest mismatch: "+original)

    destination.mkdir(parents=False,mode=0o700,exist_ok=False)
    for source,relative in FILES.items():
        file=destination / relative
        file.parent.mkdir(parents=True,exist_ok=True)
        with file.open("xb") as output:
            output.write(selected[source])

    return {
        **evidence,
        "source_files_staged": len(FILES),
        "source_manifest_checks_passed": True,
        "frontend_runtime_built": False,
        "production_frontend_modified": False
    }


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive",type=Path,required=True)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        report=stage_foundations(args.archive.read_bytes(),args.output_dir)
    except (ValueError,OSError,KeyError,tarfile.TarError) as exc:
        print("GC UI STAGE FAIL: "+type(exc).__name__,file=sys.stderr)
        return 2
    print("GC UI STAGE PASS: four exact source modules/styles matched pinned Foundations provenance")
    print("Scope: local demo only; no npm scripts, Home Assistant frontend replacement or release")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
