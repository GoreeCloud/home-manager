#!/usr/bin/env python3
"""Python 3.14 AST-only inspection of the pinned PyRIC source distribution.

No PyRIC setup.py, modules, device APIs or kernel socket calls are imported,
compiled into executable bytecode, built, installed or executed. This produces
a review diagnostic, not compatibility or security clearance.
"""

from __future__ import annotations

import argparse
import ast
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tarfile
import tokenize

import inspect_pyric_sdist as guard

MAX_SOURCE_FILE = 360_000
MAX_PYTHON_FILES = 150
MAX_PYTHON_BYTES = 8_000_000
CAPABILITY_MODULES = frozenset({
    "socket", "fcntl", "subprocess", "ctypes", "os", "pwd", "grp", "signal",
})


def analyze_archive(content: bytes, *, check_hash: bool = True) -> dict[str, object]:
    """Inspect all bounded Python source text after the inert TAR preflight."""
    provenance = guard.inspect_archive(content, check_hash=check_hash)
    code_units = 0
    total_bytes = 0
    syntax_errors: list[str] = []
    sensitive_imports: set[str] = set()
    dynamic_call_sites: dict[str, int] = {"eval": 0, "exec": 0, "__import__": 0}
    with tarfile.open(fileobj=BytesIO(content), mode="r:gz") as archive:
        for member in archive:
            name = member.name
            parts = PurePosixPath(name).parts
            if not member.isfile() or not name.endswith(".py"):
                continue
            if len(parts) < 2 or (
                len(parts) > 2 and parts[1] != "pyric"
                and name.lower().split("/", 1)[1] != "setup.py"
            ):
                continue
            if member.size > MAX_SOURCE_FILE:
                raise ValueError("oversized Python source member")
            code_units += 1
            total_bytes += member.size
            if code_units > MAX_PYTHON_FILES or total_bytes > MAX_PYTHON_BYTES:
                raise ValueError("too many Python source files or bytes")
            reader = archive.extractfile(member)
            if reader is None:
                raise ValueError("unreadable Python source")
            raw = reader.read(member.size + 1)
            if len(raw) != member.size:
                raise ValueError("truncated Python source member")
            relative = "/".join(parts[1:])
            try:
                # Tokenizer detects PEP 263 encodings; ast.parse does NOT execute.
                encoding, _ = tokenize.detect_encoding(BytesIO(raw).readline)
                tree = ast.parse(raw.decode(encoding), filename=relative)
            except (SyntaxError, UnicodeError, LookupError):
                syntax_errors.append(relative)
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    sensitive_imports.update(
                        alias.name.split(".", 1)[0] for alias in node.names
                        if alias.name.split(".", 1)[0] in CAPABILITY_MODULES
                    )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".", 1)[0]
                    if root in CAPABILITY_MODULES:
                        sensitive_imports.add(root)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id in dynamic_call_sites:
                        dynamic_call_sites[node.func.id] += 1
    if code_units < 8:
        raise ValueError("unexpectedly sparse PyRIC Python source archive")
    return {
        "scope": "inert Python 3.14.10 parser diagnostic only",
        "pypi_sha256": provenance["sha256"],
        "python_files_parsed_or_attempted": code_units,
        "python_syntax_errors": sorted(syntax_errors),
        "sensitive_module_import_names_observed": sorted(sensitive_imports),
        "dynamic_call_syntax_counts": dynamic_call_sites,
        "source_executed": False,
        "wireless_devices_accessed": False,
        "GPL_source_notice": True,
        "upstream_0_1_6_3_tag_verified": False,
        "runtime_compatible_verified": False,
        "release_ready": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args(argv)
    if sys.version_info[:3] != (3, 14, 10) or sys.platform != "linux":
        print("STATIC SOURCE FAIL: expected Linux Python 3.14.10 runner", file=sys.stderr)
        return 2
    try:
        metadata = json.loads(guard.read_bounded(guard.PYPI_JSON, guard.MAX_JSON_BYTES))
        url = guard.select_release(metadata)
        report = analyze_archive(guard.read_bounded(url, guard.MAX_ARCHIVE_BYTES))
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (ValueError, OSError, UnicodeError, tarfile.TarError, json.JSONDecodeError) as exc:
        print("STATIC SOURCE FAIL: " + type(exc).__name__, file=sys.stderr)
        return 2
    print(f"PYRIC AST INVENTORY: {report['python_files_parsed_or_attempted']} source files; "
          f"{len(report['python_syntax_errors'])} syntax/decode failures")
    for filename in report["python_syntax_errors"]:
        print("PYRIC SYNTAX GAP: " + filename)
    print("Import names requiring security review: " + ", ".join(report["sensitive_module_import_names_observed"]))
    print("RELEASE BLOCKED: AST parsing is not import/runtime, GPL or security clearance; no device access")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
