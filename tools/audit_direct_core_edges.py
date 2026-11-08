#!/usr/bin/env python3
"""Audit one-hop, published dependencies of pinned Home Manager Core packages.

Only read bounded PyPI release JSON. Never download, install, import, execute,
build or resolve third-party packages. Compare active Requires-Dist edges
against other exact direct Core pins, not the full transitive dependency
closure. Optional extras are not enabled; this is a diagnostic, not a lock.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
from typing import Any

from pip._vendor.packaging.markers import default_environment
from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.utils import canonicalize_name

from audit_direct_core_wheels import MAX_WORKERS, fetch_release, parse_direct_requirements


def inspect_metadata(
    name: str,
    version: str,
    metadata: dict[str, Any],
    pins: dict[str, str],
    environment: dict[str, str],
) -> dict[str, Any]:
    """Compare one release's declared active dependencies against direct pins."""
    info = metadata.get("info")
    if not isinstance(info, dict):
        raise ValueError("PyPI release info is absent")
    if info.get("version") != version:
        raise ValueError("PyPI returned a different package version")
    requires_dist = info.get("requires_dist")
    if requires_dist is None:
        return {"name": name, "version": version, "state": "requires_dist_unknown", "comparisons": 0, "conflicts": []}
    if not isinstance(requires_dist, list) or len(requires_dist) > 300:
        raise ValueError("PyPI Requires-Dist has an unexpected shape")
    comparisons = 0
    conflicts: list[dict[str, str]] = []
    unknown_specifiers: set[str] = set()
    for line in requires_dist:
        if not isinstance(line, str) or len(line) > 1200:
            raise ValueError("invalid Requires-Dist entry")
        requirement = Requirement(line)
        requirement_name = canonicalize_name(requirement.name)
        if requirement.marker is not None and not requirement.marker.evaluate(environment):
            continue
        direct_version = pins.get(requirement_name)
        if direct_version is None:
            continue
        if requirement.url or requirement.extras:
            unknown_specifiers.add(requirement_name)
            continue
        comparisons += 1
        if requirement.specifier and direct_version not in requirement.specifier:
            conflicts.append({
                "dependency": requirement_name,
                "required": str(requirement.specifier),
                "direct_pin": direct_version,
            })
    return {
        "name": name,
        "version": version,
        "state": "examined" if not unknown_specifiers else "partially_unassessed",
        "comparisons": comparisons,
        "conflicts": sorted(conflicts, key=lambda x: (x["dependency"], x["required"])),
        "unsupported_edges": sorted(unknown_specifiers),
    }


def audit_edges(
    pins: list[tuple[str, str]],
    *,
    fetcher: Any = fetch_release,
    environment: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    pin_index = dict(pins)
    env = default_environment() if environment is None else dict(environment)
    env["extra"] = ""

    def one(item: tuple[str, str]) -> dict[str, Any]:
        name, version = item
        try:
            return inspect_metadata(name, version, fetcher(name, version), pin_index, env)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            return {
                "name": name,
                "version": version,
                "state": "metadata_error_" + type(exc).__name__,
                "comparisons": 0,
                "conflicts": [],
            }

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        return sorted(pool.map(one, pins), key=lambda x: x["name"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)
    if sys.version_info[:3] != (3, 14, 10) or sys.platform != "linux":
        print("EDGE FAIL: requires pinned Linux Python 3.14.10", file=sys.stderr)
        return 2
    try:
        pins, ranges = parse_direct_requirements(args.requirements.read_text(encoding="utf-8"))
        edges = audit_edges(pins)
        report = {
            "scope": "first-level Requires-Dist of exact pinned Core releases, default extras, Python 3.14.10 Linux",
            "pin_count": len(pins),
            "excluded_ranges": ranges,
            "results": edges,
        }
        args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print("EDGE FAIL: " + type(exc).__name__, file=sys.stderr)
        return 2
    failures = [r for r in edges if r["state"].startswith("metadata_error_")]
    unknown = [r for r in edges if r["state"] in {"requires_dist_unknown", "partially_unassessed"}]
    conflicts = [(r["name"], r["version"], conflict) for r in edges for conflict in r["conflicts"]]
    print(f"ONE-HOP PIN AUDIT: {len(pins)} packages, "
          f"{sum(r['comparisons'] for r in edges)} direct-pin edges, "
          f"{len(conflicts)} potential pin conflicts, {len(unknown)} incomplete declarations, "
          f"{len(failures)} metadata errors, {len(ranges)} unassessed version ranges")
    for source, version, conflict in conflicts:
        print(f"PIN CONFLICT: {source}=={version} requires "
              f"{conflict['dependency']}{conflict['required']} "
              f"but Core directly pins {conflict['dependency']}=={conflict['direct_pin']}")
    for item in unknown + failures:
        print(f"EDGE UNKNOWN: {item['name']}=={item['version']} ({item['state']})")
    print("Scope: first-level metadata-only; no install, execution or full transitive solver")
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
