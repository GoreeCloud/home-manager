"""Isolated tests of wheel metadata checks; no upstream package is executed."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / "tools/check_home_manager_wheel.py"
SPEC = importlib.util.spec_from_file_location("home_manager_wheel_guard", SCRIPT)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def make_wheel(path: Path, *, overrides: dict[str, str | None] | None = None) -> None:
    prefix = "homeassistant-2026.11.0.dist-info/"
    contents = {
        prefix + "METADATA": (
            "Metadata-Version: 2.4\nName: homeassistant\nVersion: 2026.11.0\n"
            "License-Expression: Apache-2.0\n"
            "Summary: GoreeCloud Home Manager development import of Home Assistant Core.\n"
            "Classifier: Development Status :: 3 - Alpha\n"
            "Project-URL: Homepage, https://github.com/GoreeCloud/home-manager\n"
            "Project-URL: Source Code, https://github.com/GoreeCloud/home-manager\n"
            "Project-URL: Bug Reports, https://github.com/GoreeCloud/home-manager/issues\n"
            "Project-URL: Upstream Core Source, https://github.com/home-assistant/core\n"
            "Project-URL: Upstream Frontend Source, https://github.com/home-assistant/frontend\n"
        ),
        prefix + "entry_points.txt": (
            "[console_scripts]\nhass = homeassistant.__main__:main\n"
            "goreecloud-home-manager = homeassistant.__main__:main\n"
        ),
        prefix + "licenses/LICENSE.md": (
            "                                 Apache License\n"
            "                           Version 2.0, January 2004\n"
        ),
        "homeassistant/__main__.py": "# test fixture only\n",
    }
    for name, value in (overrides or {}).items():
        if value is None:
            contents.pop(name, None)
        else:
            contents[name] = value
    with ZipFile(path, "w") as archive:
        for name, content in contents.items():
            archive.writestr(name, content)


class HomeManagerWheelGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.wheel = self.root / "homeassistant-2026.11.0-py3-none-any.whl"
        make_wheel(self.wheel)

    def test_valid_wheel_fixture_passes(self) -> None:
        self.assertEqual(guard.inspect(self.wheel), [])

    def test_cli_mismatch_is_rejected(self) -> None:
        make_wheel(
            self.wheel,
            overrides={
                "homeassistant-2026.11.0.dist-info/entry_points.txt":
                "[console_scripts]\nhass = homeassistant.__main__:main\n"
                "goreecloud-home-manager = untrusted:start\n",
            },
        )
        self.assertTrue(any("alias" in s for s in guard.inspect(self.wheel)))

    def test_missing_license_is_rejected(self) -> None:
        make_wheel(
            self.wheel,
            overrides={"homeassistant-2026.11.0.dist-info/licenses/LICENSE.md": None},
        )
        self.assertTrue(any("license" in s for s in guard.inspect(self.wheel)))

    def test_bad_license_metadata_is_rejected(self) -> None:
        make_wheel(
            self.wheel,
            overrides={
                "homeassistant-2026.11.0.dist-info/METADATA":
                "Metadata-Version: 2.4\nName: homeassistant\nVersion: 2026.11.0\n"
            },
        )
        self.assertTrue(any("Apache" in s for s in guard.inspect(self.wheel)))

    def test_stable_maturity_claim_is_rejected(self) -> None:
        metadata = "homeassistant-2026.11.0.dist-info/METADATA"
        with ZipFile(self.wheel) as archive:
            text = archive.read(metadata).decode("utf-8")
        make_wheel(
            self.wheel,
            overrides={metadata: text.replace(
                "Development Status :: 3 - Alpha",
                "Development Status :: 5 - Production/Stable",
            )},
        )
        self.assertTrue(any("maturity" in problem for problem in guard.inspect(self.wheel)))

    def test_missing_upstream_provenance_url_is_rejected(self) -> None:
        metadata = "homeassistant-2026.11.0.dist-info/METADATA"
        with ZipFile(self.wheel) as archive:
            text = archive.read(metadata).decode("utf-8")
        make_wheel(
            self.wheel,
            overrides={metadata: text.replace(
                "Project-URL: Upstream Core Source, https://github.com/home-assistant/core\\n",
                "",
            )},
        )
        self.assertTrue(any("URL" in problem for problem in guard.inspect(self.wheel)))

    def test_member_path_traversal_is_rejected(self) -> None:
        make_wheel(self.wheel, overrides={"../../outside.txt": "invalid\n"})
        self.assertTrue(any("unsafe" in s for s in guard.inspect(self.wheel)))

    def test_invalid_archive_is_rejected(self) -> None:
        self.wheel.write_bytes(b"not a wheel")
        self.assertTrue(guard.inspect(self.wheel))

    def test_cli_detects_one_valid_wheel(self) -> None:
        self.assertEqual(guard.main(["--wheel-dir", str(self.root)]), 0)

    def test_cli_fails_with_multiple_wheels(self) -> None:
        make_wheel(self.root / "homeassistant-2026.11.0-2-py3-none-any.whl")
        self.assertEqual(guard.main(["--wheel-dir", str(self.root)]), 2)


if __name__ == "__main__":
    unittest.main()
