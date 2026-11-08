"""Synthetic tests for pinned frontend wheel provenance; no upstream code runs."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

SOURCE = Path(__file__).resolve().parents[1] / "tools/check_home_manager_frontend_artifact.py"
SPEC = importlib.util.spec_from_file_location("frontend_artifact_guard", SOURCE)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def make_wheel(path: Path, overrides: dict[str, str | None] | None = None) -> None:
    prefix = "home_assistant_frontend-20261028.4.dist-info/"
    contents: dict[str, str] = {
        prefix + "METADATA": (
            "Metadata-Version: 2.4\n"
            "Name: home-assistant-frontend\n"
            "Version: 20261028.4\n"
            "License-Expression: Apache-2.0\n"
        ),
        prefix + "licenses/LICENSE.md": (
            "                                 Apache License\n"
            "                           Version 2.0, January 2004\n"
        ),
        prefix + "WHEEL": "Wheel-Version: 1.0\nGenerator: synthetic-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        "hass_frontend/__init__.py": "# fixture, never imported\n",
    }
    for key, value in (overrides or {}).items():
        if value is None:
            contents.pop(key, None)
        else:
            contents[key] = value
    with ZipFile(path, "w") as archive:
        for name, value in contents.items():
            archive.writestr(name, value)


class FrontendArtifactTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.wheel = self.folder / guard.FILENAME
        make_wheel(self.wheel)

    def failures(self) -> list[str]:
        return guard.inspect(self.wheel, verify_digest=False)

    def test_synthetic_valid_wheel(self) -> None:
        self.assertEqual(self.failures(), [])

    def test_wrong_sha256_rejected(self) -> None:
        self.assertTrue(any("SHA-256" in err for err in guard.inspect(self.wheel)))

    def test_missing_license_rejected(self) -> None:
        make_wheel(
            self.wheel,
            {"home_assistant_frontend-20261028.4.dist-info/licenses/LICENSE.md": None},
        )
        self.assertTrue(any("license" in err for err in self.failures()))

    def test_non_apache_license_rejected(self) -> None:
        make_wheel(
            self.wheel,
            {"home_assistant_frontend-20261028.4.dist-info/METADATA":
             "Metadata-Version: 2.4\nName: home-assistant-frontend\n"
             "Version: 20261028.4\nLicense-Expression: MIT\n"},
        )
        self.assertTrue(any("license" in err for err in self.failures()))

    def test_missing_assets_rejected(self) -> None:
        make_wheel(self.wheel, {"hass_frontend/__init__.py": None})
        self.assertTrue(any("asset" in err for err in self.failures()))

    def test_zip_traversal_rejected(self) -> None:
        make_wheel(self.wheel, {"../escape": "bad"})
        self.assertTrue(any("unsafe" in err for err in self.failures()))

    def test_wrong_filename_rejected(self) -> None:
        other = self.folder / "frontend-unpinned.whl"
        other.write_bytes(self.wheel.read_bytes())
        self.assertTrue(any("named" in err for err in guard.inspect(other, verify_digest=False)))

    def test_hosted_job_is_scoped_and_uses_binary_only_download(self) -> None:
        workflow = SOURCE.parents[1] / ".github/workflows/home-manager-import-checks.yml"
        content = workflow.read_text(encoding="utf-8")
        self.assertIn("frontend-artifact-smoke:", content)
        self.assertIn("github.head_ref == 'feat/frontend-wheel-provenance-20261108'", content)
        self.assertIn("--no-deps --only-binary=:all:", content)
        self.assertIn(guard.VERSION, content)

    def test_corrupted_archive_rejected(self) -> None:
        self.wheel.write_bytes(b"not a zip archive")
        self.assertTrue(self.failures())


if __name__ == "__main__":
    unittest.main()
