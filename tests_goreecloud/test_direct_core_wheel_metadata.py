"""No-network regression tests for the Core direct wheel metadata inventory."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

from pip._vendor.packaging.tags import Tag

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools/audit_direct_core_wheels.py"
SPEC = importlib.util.spec_from_file_location("goreecloud_direct_wheel_metadata", MODULE_PATH)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

HOST_TAG = Tag("cp314", "cp314", "manylinux_2_28_x86_64")
ABI_TAG = Tag("cp39", "abi3", "manylinux_2_28_x86_64")
OTHER_TAG = Tag("cp312", "cp312", "manylinux_2_28_x86_64")
TAGS = frozenset({HOST_TAG, ABI_TAG})
VALID_HASH = "c" * 64


def file_info(filename: str, *, requires_python: str = ">=3.9") -> dict:
    return {
        "filename": filename,
        "digests": {"sha256": VALID_HASH},
        "requires_python": requires_python,
        "yanked": False,
    }


def fixture_requirements() -> str:
    rows = ["# Inherited Core dependency pins", "-c homeassistant/package_constraints.txt"]
    rows += [f"fixture-package-{i}==1.0.0" for i in range(20)]
    rows += ["certifi>=2021.5.30", "typing-extensions>=4.16,<5"]
    return "\n".join(rows) + "\n"


class CoreDirectWheelMetadataTests(unittest.TestCase):
    def test_parse_fixed_pins_and_keep_ranges_explicit(self) -> None:
        pins, ranges = audit.parse_direct_requirements(fixture_requirements())
        self.assertEqual(len(pins), 20)
        self.assertEqual(len(ranges), 2)
        self.assertEqual(pins[0], ("fixture-package-0", "1.0.0"))

    def test_reject_url_and_nested_requirements_directives(self) -> None:
        with self.assertRaises(ValueError):
            audit.parse_direct_requirements(fixture_requirements() + "-r other.txt\n")
        with self.assertRaises(ValueError):
            audit.parse_direct_requirements(fixture_requirements() + "hack @ https://bad.invalid/a.whl\n")

    def test_reject_duplicate_requirement(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit.parse_direct_requirements(fixture_requirements() + "fixture_package_0==1.0.0\n")

    def test_native_exact_py314_wheel_matches(self) -> None:
        files = {"urls": [file_info("fixture_package-1.0.0-cp314-cp314-manylinux_2_28_x86_64.whl")]}
        self.assertEqual(audit.classify_release("fixture-package", "1.0.0", files, TAGS, "3.14.10"), "compatible_wheel_metadata")

    def test_abi3_wheel_matches_without_legacy_cp312_wheel(self) -> None:
        files = {"urls": [
            file_info("fixture_package-1.0.0-cp312-cp312-manylinux_2_28_x86_64.whl"),
            file_info("fixture_package-1.0.0-cp39-abi3-manylinux_2_28_x86_64.whl"),
        ]}
        self.assertEqual(audit.classify_release("fixture-package", "1.0.0", files, TAGS, "3.14.10"), "compatible_wheel_metadata")

    def test_old_platform_and_sdist_fail_explicitly(self) -> None:
        old = {"urls": [file_info("fixture_package-1.0.0-cp312-cp312-manylinux_2_28_x86_64.whl")]}
        sdist = {"urls": [{"filename": "fixture_package-1.0.0.tar.gz"}]}
        self.assertEqual(audit.classify_release("fixture-package", "1.0.0", old, TAGS, "3.14.10"), "no_matching_wheel")
        self.assertEqual(audit.classify_release("fixture-package", "1.0.0", sdist, TAGS, "3.14.10"), "source_only")

    def test_python_requires_and_yanked_are_filtered(self) -> None:
        filename = "fixture_package-1.0.0-cp39-abi3-manylinux_2_28_x86_64.whl"
        restricted = {"urls": [file_info(filename, requires_python="<3.14")]}
        self.assertEqual(audit.classify_release("fixture-package", "1.0.0", restricted, TAGS, "3.14.10"), "no_matching_wheel")
        item = file_info(filename)
        item["yanked"] = True
        self.assertEqual(audit.classify_release("fixture-package", "1.0.0", {"urls": [item]}, TAGS, "3.14.10"), "no_usable_files")

    def test_missing_hash_or_mismatched_release_rejected(self) -> None:
        item = file_info("fixture_package-1.0.0-cp314-cp314-manylinux_2_28_x86_64.whl")
        item["digests"] = {}
        with self.assertRaises(ValueError):
            audit.classify_release("fixture-package", "1.0.0", {"urls": [item]}, TAGS, "3.14.10")
        item["digests"] = {"sha256": VALID_HASH}
        with self.assertRaises(ValueError):
            audit.classify_release("other-name", "1.0.0", {"urls": [item]}, TAGS, "3.14.10")

    def test_audit_pin_classifications_dont_download_third_party_content(self) -> None:
        data = {
            "first": {"urls": [file_info("first-1.0.0-cp39-abi3-manylinux_2_28_x86_64.whl")]},
            "second": {"urls": [{"filename": "second-1.0.0.tar.gz"}]},
        }
        requested = []

        def fake_fetch(name: str, version: str) -> dict:
            requested.append((name, version))
            return data[name]

        items = audit.audit_pins([("second", "1.0.0"), ("first", "1.0.0")], fetcher=fake_fetch, tags=TAGS)
        self.assertEqual([item["name"] for item in items], ["first", "second"])
        self.assertEqual([item["status"] for item in items], ["compatible_wheel_metadata", "source_only"])
        self.assertCountEqual(requested, [("first", "1.0.0"), ("second", "1.0.0")])

    def test_metadata_fetch_error_is_explicitly_reported(self) -> None:
        def bad_fetch(name: str, version: str) -> dict:
            raise OSError("simulated network failure")

        results = audit.audit_pins([("first", "1.0.0")], fetcher=bad_fetch, tags=TAGS)
        self.assertEqual(results[0]["status"], "metadata_error_OSError")

    def test_guarded_runner_requires_pinned_python_and_no_execution(self) -> None:
        workflow = (ROOT / ".github/workflows/home-manager-import-checks.yml").read_text(encoding="utf-8")
        self.assertIn("direct-core-wheel-metadata-inventory:", workflow)
        self.assertIn("github.head_ref == 'ci/direct-wheel-metadata-inventory-20261108'", workflow)
        self.assertIn("python tools/audit_direct_core_wheels.py", workflow)
        self.assertIn("python-version-file: .python-version", workflow)


if __name__ == "__main__":
    unittest.main()
