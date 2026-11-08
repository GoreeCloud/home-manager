#!/usr/bin/env python3
"""Read-only, dependency-free checks for the Home Manager source import.

This is a narrowly scoped import-invariant gate, NOT a malware, vulnerability,
license-compatibility, build, runtime, or UI acceptance test.
"""

from __future__ import annotations

import argparse
import json
import tomllib
from pathlib import Path
import sys
from typing import Final

UPSTREAM_SHA: Final = "74cf5a49c63ed8d4d87717844bf14f79c28c9cea"
PRODUCT_NAME: Final = "GoreeCloud Home Manager"
APPROVED_WORKFLOWS: Final = frozenset({"home-manager-import-checks.yml"})
BLOCKED_ACTIVE_PATHS: Final = (
    ".github/CODEOWNERS",
    ".github/FUNDING.yml",
    ".github/renovate.json",
    ".github/dependabot.yml",
    ".github/ISSUE_TEMPLATE",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/copilot-instructions.md",
    ".github/aw",
    ".agents",
    ".claude",
    ".gemini",
    "AGENTS.md",
    "CLAUDE.md",
)
MAX_TEXT_BYTES: Final = 1_000_000


def _read_text(root: Path, relative_path: str) -> str:
    """Read only a bounded regular file from inside the selected checkout."""
    file = root / relative_path
    if file.is_symlink() or not file.is_file():
        raise ValueError(f"missing or unsafe regular file: {relative_path}")
    if not file.resolve(strict=True).is_relative_to(root):
        raise ValueError(f"file resolves outside checkout: {relative_path}")
    if file.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError(f"file exceeds read bound: {relative_path}")
    return file.read_text(encoding="utf-8")


def evaluate(root: Path) -> list[dict[str, object]]:
    """Evaluate import safeguards without importing or executing upstream code."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("the repository root must be a directory")
    checks: list[dict[str, object]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    def contains(name: str, path: str, fragments: tuple[str, ...]) -> None:
        try:
            text = _read_text(root, path)
            passed = all(fragment in text for fragment in fragments)
            record(name, passed, "expected source markers present" if passed else "required markers missing")
        except (OSError, UnicodeError, ValueError) as exc:
            record(name, False, str(exc))

    contains(
        "upstream-license",
        "LICENSE.md",
        ("Apache License", "Version 2.0, January 2004", "TERMS AND CONDITIONS FOR USE"),
    )
    contains(
        "goreecloud-product-identity",
        "README.rst",
        (PRODUCT_NAME, UPSTREAM_SHA, "UPSTREAM_README.rst", "Apache License 2.0"),
    )
    contains(
        "upstream-provenance",
        "UPSTREAM_SOURCE.md",
        (UPSTREAM_SHA, "home-assistant/core", "Apache-2.0", "fresh root commit"),
    )
    contains(
        "security-reporting",
        "SECURITY.md",
        ("GoreeCloud Home Manager", "admin@goreecloud.com", "not"),
    )
    contains(
        "original-upstream-readme",
        "UPSTREAM_README.rst",
        ("Home Assistant", "home-assistant.io"),
    )
    # Runtime identifiers must remain compatible until a dedicated migration is tested.
    contains(
        "package-compatibility",
        "pyproject.toml",
        ('name = "homeassistant"', 'requires-python = ">=3.14.2"'),
    )
    # Catch accidental partial-content uploads of this large upstream TOML file.
    contains(
        "upstream-python-tooling-preserved",
        "pyproject.toml",
        ("[tool.setuptools]", "[tool.pytest.ini_options]",
         "[tool.ruff]", "[tool.ruff.lint.pydocstyle]"),
    )
    contains(
        "frontend-compatibility",
        "homeassistant/components/frontend/manifest.json",
        ('"domain": "frontend"', '"home-assistant-frontend==20261028.4"'),
    )
    contains(
        "supported-python-source-pin",
        ".python-version",
        ("3.14.10",),
    )
    contains(
        "application-identifier",
        "homeassistant/const.py",
        ('APPLICATION_NAME: Final = "HomeAssistant"',),
    )

    try:
        project = tomllib.loads(_read_text(root, "pyproject.toml"))["project"]
        commands = project["scripts"]
        upstream_entry = "homeassistant.__main__:main"
        matching = (
            commands.get("hass") == upstream_entry
            and commands.get("goreecloud-home-manager") == upstream_entry
        )
        record(
            "goreecloud-cli-alias",
            matching,
            "both commands target the same core entrypoint"
            if matching else "branded and upstream entrypoints are missing or inconsistent",
        )
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        record("goreecloud-cli-alias", False, f"invalid package script metadata: {exc}")

    workflows = root / ".github/workflows"
    if workflows.exists() and (workflows.is_symlink() or not workflows.is_dir()):
        record("active-workflows", False, "workflow directory is not a safe regular directory")
    else:
        actual = {p.name for p in workflows.iterdir()} if workflows.exists() else set()
        passed = actual == APPROVED_WORKFLOWS and all(
            (workflows / name).is_file() and not (workflows / name).is_symlink()
            for name in actual
        )
        record(
            "active-workflows",
            passed,
            f"active workflow filenames: {', '.join(sorted(actual)) or '(none)'}",
        )

    disabled = root / ".github/upstream-workflows-disabled"
    if disabled.is_dir() and not disabled.is_symlink():
        retained = sum(p.is_file() and not p.is_symlink() for p in disabled.iterdir())
    else:
        retained = 0
    record(
        "retained-upstream-workflows",
        retained >= 19,
        f"retained inactive files: {retained} (expected >=19)",
    )

    contains(
        "workflow-permission-scope",
        ".github/workflows/home-manager-import-checks.yml",
        ("permissions:\n  contents: read",
         "persist-credentials: false",
         "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
         "actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c",
         "github.event.pull_request.head.repo.full_name == 'GoreeCloud/home-manager'"),
    )
    contains(
        "binary-only-core-dependency-plan",
        ".github/workflows/home-manager-import-checks.yml",
        ("--isolated install --dry-run --ignore-installed --only-binary=:all:",
         "--index-url https://pypi.org/simple",
         "core-deps-report.json",
         "no installs"),
    )
    conflicts = [
        p for p in BLOCKED_ACTIVE_PATHS
        if (root / p).exists() or (root / p).is_symlink()
    ]
    record(
        "upstream-automation-quarantine",
        not conflicts,
        "no inherited active automation" if not conflicts
        else "unexpected active paths: " + ", ".join(conflicts),
    )

    # Audits intentionally do not scan credentials, modify the working tree,
    # install packages, contact the network, or execute upstream modules.
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent.parent,
        help="Explicit repository root; defaults to the script's parent checkout",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable result")
    args = parser.parse_args(argv)
    try:
        checks = evaluate(args.root)
    except (OSError, ValueError) as exc:
        print(f"import preflight unavailable: {exc}", file=sys.stderr)
        return 2
    failures = sum(not check["passed"] for check in checks)
    if args.json:
        print(json.dumps(
            {"product": PRODUCT_NAME, "scope": "static-import-invariants-only",
             "passed": failures == 0, "checks": checks},
            sort_keys=True, indent=2,
        ))
    else:
        for check in checks:
            status = "PASS" if check["passed"] else "FAIL"
            print(f"{status}: {check['name']} — {check['detail']}")
        print(f"Static import gate: {len(checks) - failures}/{len(checks)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
