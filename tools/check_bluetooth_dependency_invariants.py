#!/usr/bin/env python3
"""Read-only source guard for imported privileged Bluetooth dependency edges.

This is an invariant/triage check, never a runtime capability or permission
approval. Do not import, install, call or execute PyRIC or Bluetooth recovery.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SOURCE_FILES = (
    "homeassistant/components/bluetooth/manifest.json",
    "homeassistant/package_constraints.txt",
    "requirements.txt",
    "homeassistant/components/bluetooth/__init__.py",
)
MANIFEST_PINS = frozenset({
    "bluetooth-auto-recovery==1.6.4",
    "habluetooth==7.1.2",
    "bluetooth-adapters==2.4.0",
})
CONSTRAINT_PINS = MANIFEST_PINS | frozenset({"home-assistant-bluetooth==2.0.0"})
DIRECT_PIN = "home-assistant-bluetooth==2.0.0"
MAX_BYTES = 170_000


def _read(root: Path, relative: str) -> str:
    source = root / relative
    if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(root):
        raise ValueError("missing or unsafe inherited Bluetooth source")
    if source.stat().st_size > MAX_BYTES:
        raise ValueError("Bluetooth source exceeds inspection bounds")
    return source.read_text("utf-8")


def _lines(text: str) -> list[str]:
    return [line.split("#", 1)[0].strip() for line in text.splitlines() if line.strip()]


def audit(root: Path) -> dict[str, object]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("repository root must be a real directory")
    manifest = json.loads(_read(root, SOURCE_FILES[0]))
    if not isinstance(manifest, dict) or manifest.get("domain") != "bluetooth":
        raise ValueError("unexpected imported Bluetooth manifest")
    req = manifest.get("requirements")
    loggers = manifest.get("loggers")
    if not isinstance(req, list) or not all(isinstance(x, str) for x in req) or len(req) != len(set(req)):
        raise ValueError("unexpected Bluetooth requirements")
    if not isinstance(loggers, list) or "bluetooth_auto_recovery" not in loggers:
        raise ValueError("Bluetooth recovery logger/reference changed; re-review needed")
    if any(pin not in req for pin in MANIFEST_PINS):
        raise ValueError("Bluetooth recovery version changed without security review")
    c = _lines(_read(root, SOURCE_FILES[1]))
    d = _lines(_read(root, SOURCE_FILES[2]))
    for pin in sorted(CONSTRAINT_PINS):
        if c.count(pin) != 1:
            raise ValueError("pinned Bluetooth dependency constraints changed")
    if d.count(DIRECT_PIN) != 1:
        raise ValueError("direct Home Assistant Bluetooth library pin changed")
    source = _read(root, SOURCE_FILES[3])
    if "from habluetooth import (" not in source or "async def async_setup(" not in source:
        raise ValueError("Home Assistant Bluetooth lifecycle structure changed")
    # This is only direct imported manifest/constraint identity, not an audit
    # of any transitive wheel, package metadata or actual recovery call site.
    return {
        "imported_manifest_pin_count": len(MANIFEST_PINS),
        "direct_home_assistant_bluetooth_pin": DIRECT_PIN,
        "upstream_recovery_package": "bluetooth-auto-recovery==1.6.4",
        "known_transitive_pyric": "PyRIC>=0.1.6.3 (from prior pinned source/solver evidence)",
        "core_bluetooth_source_unchanged": True,
        "native_recovery_privilege_review_complete": False,
        "full_dependency_graph_solved": False,
        "bluetooth_device_operations_performed": False,
        "license_compatibility_approved": False,
        "release_ready": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = audit(args.root)
        if args.report.is_symlink():
            raise ValueError("refusing symlink report")
        args.report.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, UnicodeError, TypeError, KeyError, json.JSONDecodeError):
        print("BLUETOOTH IMPORT INVARIANTS FAIL; re-review source/permissions", file=sys.stderr)
        return 2
    print("BLUETOOTH SOURCE INVARIANTS PASS: exact imported manifest/direct/constraint pins")
    print("RELEASE BLOCKED: PyRIC provenance/license/privileged recovery not approved or run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
