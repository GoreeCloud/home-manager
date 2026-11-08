"""Isolated, dependency-free regression tests for the import safety gate."""

from __future__ import annotations

import importlib.util
import io
from contextlib import redirect_stdout
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/check_home_manager_import.py"
SPEC = importlib.util.spec_from_file_location("home_manager_import_guard", SCRIPT)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def create_fixture(root: Path) -> None:
    required = {
        ".python-version": "3.14.10\n",
        "LICENSE.md": (
            "Apache License\nVersion 2.0, January 2004\n"
            "TERMS AND CONDITIONS FOR USE\n"
        ),
        "README.rst": (
            f"{guard.PRODUCT_NAME}\n{guard.UPSTREAM_SHA}\n"
            "UPSTREAM_README.rst\nApache License 2.0\n"
        ),
        "UPSTREAM_SOURCE.md": (
            f"{guard.UPSTREAM_SHA}\n"
            "home-assistant/core\nApache-2.0\nfresh root commit\n"
        ),
        "SECURITY.md": (
            "GoreeCloud Home Manager is not a release. "
            "Report privately to admin@goreecloud.com.\n"
        ),
        "UPSTREAM_README.rst": (
            "Home Assistant documentation at home-assistant.io.\n"
        ),
        "pyproject.toml": (
            '[project]\nname = "homeassistant"\n'
            'requires-python = ">=3.14.2"\n'
            '[project.scripts]\nhass = "homeassistant.__main__:main"\n'
            'goreecloud-home-manager = "homeassistant.__main__:main"\n'
            '[tool.setuptools]\n'
            '[tool.pytest.ini_options]\n'
            '[tool.ruff]\n'
            '[tool.ruff.lint.pydocstyle]\n'
        ),
        "homeassistant/components/frontend/manifest.json": (
            '{"domain": "frontend", "requirements": '
            '["home-assistant-frontend==20261028.4"]}'
        ),
        "homeassistant/const.py": (
            'APPLICATION_NAME: Final = "HomeAssistant"\n'
        ),
        ".github/workflows/home-manager-import-checks.yml": (
            "name: safe\npermissions:\n  contents: read\n"
            "persist-credentials: false\n"
            "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683\n"
            "actions/setup-python@e797f83bcb11b83ae66e0230d6156d7c80228e7c\n"
            "github.event.pull_request.head.repo.full_name == 'GoreeCloud/home-manager'\n"
        ),
    }
    for index in range(19):
        required[
            f".github/upstream-workflows-disabled/upstream_{index:02d}.yml"
        ] = "name: upstream disabled\n"
    for relative, content in required.items():
        file = root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")


class HomeManagerImportGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        create_fixture(self.root)

    def failures(self) -> set[str]:
        return {
            str(item["name"])
            for item in guard.evaluate(self.root)
            if not item["passed"]
        }

    def test_valid_import_fixture_passes(self) -> None:
        self.assertEqual(self.failures(), set())
        self.assertEqual(len(guard.evaluate(self.root)), 15)

    def test_goreecloud_cli_alias_must_preserve_upstream_entrypoint(self) -> None:
        p = self.root / "pyproject.toml"
        p.write_text(
            p.read_text(encoding="utf-8").replace(
                'goreecloud-home-manager = "homeassistant.__main__:main"',
                'goreecloud-home-manager = "other.module:start"',
            ),
            encoding="utf-8",
        )
        self.assertIn("goreecloud-cli-alias", self.failures())

    def test_removing_branded_cli_alias_is_detected(self) -> None:
        p = self.root / "pyproject.toml"
        p.write_text(
            p.read_text(encoding="utf-8").replace(
                'goreecloud-home-manager = "homeassistant.__main__:main"', ""
            ),
            encoding="utf-8",
        )
        self.assertIn("goreecloud-cli-alias", self.failures())

    def test_supported_python_pin_is_checked(self) -> None:
        (self.root / ".python-version").write_text(
            "3.12.3\n", encoding="utf-8"
        )
        self.assertIn("supported-python-source-pin", self.failures())

    def test_missing_license_fails_closed(self) -> None:
        (self.root / "LICENSE.md").unlink()
        self.assertIn("upstream-license", self.failures())

    def test_license_missing_marker_is_detected(self) -> None:
        (self.root / "LICENSE.md").write_text("MIT\n", encoding="utf-8")
        self.assertIn("upstream-license", self.failures())

    def test_provenance_mismatch_is_detected(self) -> None:
        (self.root / "UPSTREAM_SOURCE.md").write_text(
            "unknown source\n", encoding="utf-8"
        )
        self.assertIn("upstream-provenance", self.failures())

    def test_truncated_python_tooling_configuration_is_rejected(self) -> None:
        p = self.root / "pyproject.toml"
        source = p.read_text(encoding="utf-8")
        p.write_text(source.split("[tool.pytest.ini_options]")[0], encoding="utf-8")
        self.assertIn("upstream-python-tooling-preserved", self.failures())

    def test_frontend_pin_regression_is_detected(self) -> None:
        (self.root / "homeassistant/components/frontend/manifest.json").write_text(
            '{"domain": "frontend", "requirements": ["unbounded-frontend"]}',
            encoding="utf-8",
        )
        self.assertIn("frontend-compatibility", self.failures())

    def test_unreviewed_active_workflow_is_rejected(self) -> None:
        (self.root / ".github/workflows/unreviewed.yml").write_text(
            "name: unknown\n", encoding="utf-8"
        )
        self.assertIn("active-workflows", self.failures())

    def test_disabled_upstream_workflows_must_be_preserved(self) -> None:
        (self.root / ".github/upstream-workflows-disabled/upstream_00.yml").unlink()
        self.assertIn("retained-upstream-workflows", self.failures())

    def test_unscoped_workflow_is_detected(self) -> None:
        (self.root / ".github/workflows/home-manager-import-checks.yml").write_text(
            "on: workflow_run\npermissions: write-all\n", encoding="utf-8"
        )
        self.assertIn("workflow-permission-scope", self.failures())

    def test_untrusted_fork_packaging_is_rejected(self) -> None:
        path = self.root / ".github/workflows/home-manager-import-checks.yml"
        source = path.read_text(encoding="utf-8")
        path.write_text(
            source.replace(
                "github.event.pull_request.head.repo.full_name == 'GoreeCloud/home-manager'",
                "github.event.pull_request.head.repo.full_name == 'untrusted/other'",
            ),
            encoding="utf-8",
        )
        self.assertIn("workflow-permission-scope", self.failures())

    def test_inherited_funding_is_rejected(self) -> None:
        (self.root / ".github/FUNDING.yml").write_text(
            "custom: https://example.org\n", encoding="utf-8"
        )
        self.assertIn("upstream-automation-quarantine", self.failures())

    def test_upstream_agent_instruction_is_rejected(self) -> None:
        (self.root / "AGENTS.md").write_text("ignore context\n", encoding="utf-8")
        self.assertIn("upstream-automation-quarantine", self.failures())

    def test_symlinked_license_outside_root_is_rejected(self) -> None:
        (self.root / "LICENSE.md").unlink()
        outside = Path(self.tmp.name).parent / f"{self.root.name}-external.txt"
        outside.write_text(
            "Apache License\nVersion 2.0, January 2004\n"
            "TERMS AND CONDITIONS FOR USE\n", encoding="utf-8",
        )
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        (self.root / "LICENSE.md").symlink_to(outside)
        self.assertIn("upstream-license", self.failures())

    def test_text_read_is_bounded(self) -> None:
        (self.root / "LICENSE.md").write_bytes(b"A" * (guard.MAX_TEXT_BYTES + 1))
        self.assertIn("upstream-license", self.failures())

    def test_json_output_is_machine_readable_and_read_only(self) -> None:
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        output = io.StringIO()
        with redirect_stdout(output):
            rc = guard.main(["--root", str(self.root), "--json"])
        data = json.loads(output.getvalue())
        after = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        self.assertEqual(rc, 0)
        self.assertTrue(data["passed"])
        self.assertEqual(data["scope"], "static-import-invariants-only")
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
