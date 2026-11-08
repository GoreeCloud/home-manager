#!/usr/bin/env python3
"""Classify a disposable uv resolution rehearsal without mislabeling failures.

A known *no-sdist* transitive blocker may be recorded as a completed DIAGNOSTIC
only. It does not satisfy dependency resolution, installation or release gates.
Unexpected failures and timeouts always fail. This script never runs packages.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

KNOWN_PYRIC_MARKERS = (
    "No solution found when resolving dependencies",
    "pyric==0.1.6.3 has no usable wheels",
    "bluetooth-auto-recovery",
    "habluetooth",
    "home-assistant-bluetooth",
)
CANDIDATES = {
    "pymicro-vad": "2.1.0",
    "pyspeex-noise": "2.0.1",
}
MAX_LOG_BYTES = 150_000
MAX_LOCK_BYTES = 400_000


def classify(status: int, solver_log: str, lock_text: str | None) -> dict[str, object]:
    """Require a coherent success lock or all exact upstream blockers."""
    if status == 0:
        if not lock_text or len(lock_text.encode("utf-8")) > MAX_LOCK_BYTES:
            raise ValueError("solver claims success without bounded result file")
        pins: dict[str, str] = {}
        for raw in lock_text.splitlines():
            line = raw.split("#", 1)[0].strip().lower()
            match = re.fullmatch(r"([a-z0-9_.-]+)==([a-z0-9._+!-]+)", line)
            if match:
                pins[match.group(1).replace("_", "-").replace(".", "-")] = match.group(2)
        for name, version in CANDIDATES.items():
            if pins.get(name) != version:
                raise ValueError("candidate resolver omitted an exact reviewed audio pin")
        if "pyturbojpeg" not in lock_text.lower() or "1.8.3" not in lock_text:
            raise ValueError("original PyTurboJPEG 1.8.3 absent from solved candidate")
        if len(pins) < 56:
            raise ValueError("candidate graph unexpectedly small")
        return {
            "status": "candidate_metadata_solved",
            "direct_source_unchanged": True,
            "resolved_exact_pins": len(pins),
            "release_ready": False,
        }

    if status == 1 and all(token in solver_log for token in KNOWN_PYRIC_MARKERS):
        return {
            "status": "blocked_source_only_pyric",
            "blocked_package": "PyRIC==0.1.6.3",
            "dependency_chain": [
                "home-assistant-bluetooth==2.0.0",
                "habluetooth==7.1.2",
                "bluetooth-auto-recovery==1.6.4",
                "pyric>=0.1.6.3",
            ],
            "release_ready": False,
            "full_dependency_graph_solved": False,
        }
    raise ValueError("unexpected solver status, unsafe new failure, or timeout")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--status", type=int, required=True)
    p.add_argument("--solver-log", type=Path, required=True)
    p.add_argument("--lock-file", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if (
            not args.solver_log.is_file()
            or args.solver_log.is_symlink()
            or args.solver_log.stat().st_size > MAX_LOG_BYTES
        ):
            raise ValueError("unbounded or missing solver log")
        log = args.solver_log.read_text(encoding="utf-8")
        lock = None
        if args.lock_file.is_file():
            if args.lock_file.is_symlink() or args.lock_file.stat().st_size > MAX_LOCK_BYTES:
                raise ValueError("unbounded or unsafe candidate lock")
            lock = args.lock_file.read_text(encoding="utf-8")
        result = classify(args.status, log, lock)
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        print("CANDIDATE DIAGNOSTIC FAIL: " + type(exc).__name__, file=sys.stderr)
        return 2
    if result["status"] == "blocked_source_only_pyric":
        print("CANDIDATE DIAGNOSTIC PASS: expected PyRIC 0.1.6.3 no-wheel blocker identified")
        print("RELEASE BLOCKED: full transitive graph NOT solved; no PyRIC source downloaded, built or run")
    else:
        print("CANDIDATE METADATA GRAPH SOLVED: version candidates only, no packages installed")
        print("RELEASE BLOCKED: security review, full installation and runtime acceptance remain open")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
