"""Dependency-free inert tests for GC UI Foundations 1.0.1 provenance guard."""

from __future__ import annotations

from io import BytesIO
import importlib.util
import json
from pathlib import Path
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools/check_gc_ui_foundations_asset.py"
SPEC = importlib.util.spec_from_file_location("gc_ui_foundations_asset_guard", PATH)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

LICENSE = b"Apache License\nVersion 2.0, January 2004\n"
MANIFEST = {
    "name": "@goreecloud/gc-ui",
    "version": "1.0.1",
    "private": False,
    "license": "Apache-2.0",
    "type": "module",
    "dependencies": {},
    "exports": {".": "./dist/index.js", "./tokens": "./dist/tokens.json",
                "./css/tokens": "./dist/tokens.css"},
}
FILES = {
    "package/package.json": json.dumps(MANIFEST).encode(),
    "package/LICENSE": LICENSE,
    "package/dist/tokens.json": b'{"name":"GC UI"}',
    "package/dist/tokens.css": b":root{--gc-space-1:4px}",
}


def fixture(
    files: dict[str, bytes] | None = None, *,
    extra: tuple[str, bytes] | None = None,
    symlink: str | None = None,
) -> bytes:
    content = BytesIO()
    with tarfile.open(fileobj=content, mode="w:gz") as tar:
        for name, payload in (FILES if files is None else files).items():
            member = tarfile.TarInfo(name)
            member.size = len(payload)
            tar.addfile(member, BytesIO(payload))
        if extra:
            member = tarfile.TarInfo(extra[0])
            member.size = len(extra[1])
            tar.addfile(member, BytesIO(extra[1]))
        if symlink:
            member = tarfile.TarInfo("package/" + symlink)
            member.type = tarfile.SYMTYPE
            member.linkname = "/etc/passwd"
            tar.addfile(member)
    return content.getvalue()


class GCUIFoundationsSourceTests(unittest.TestCase):
    def test_synthetic_stable_scoped_artifact_identity(self) -> None:
        output = guard.inspect_tgz(fixture(), verify_sha=False)
        self.assertEqual(output["version"], "1.0.1")
        self.assertEqual(output["name"], "@goreecloud/gc-ui")
        self.assertFalse(output["third_party_code_executed"])
        self.assertFalse(output["frontend_runtime_built"])
        self.assertFalse(output["goreecloud_ui_adopted"])
        self.assertFalse(output["release_ready"])

    def test_unapproved_hash_rejected_before_manifest(self) -> None:
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            guard.inspect_tgz(fixture())

    def test_traversal_and_absolute_paths_rejected(self) -> None:
        for name in ("package/../../escape.txt", "/tmp/evil.js", "package\\win.js"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    guard.inspect_tgz(fixture(extra=(name, b"untrusted")), verify_sha=False)

    def test_symlink_does_not_pass(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe"):
            guard.inspect_tgz(fixture(symlink="escape"), verify_sha=False)

    def test_unexpected_runtime_dependency_rejected(self) -> None:
        copy = dict(MANIFEST)
        copy["dependencies"] = {"some-lib": "^1.0.0"}
        files = dict(FILES)
        files["package/package.json"] = json.dumps(copy).encode()
        with self.assertRaisesRegex(ValueError, "dependencies"):
            guard.inspect_tgz(fixture(files), verify_sha=False)

    def test_incorrect_name_version_and_license_rejected(self) -> None:
        for key, val in (("name", "@other/pkg"), ("version", "1.0.0"), ("license", "GPL-3.0")):
            with self.subTest(key=key):
                manifest = dict(MANIFEST)
                manifest[key] = val
                files = dict(FILES)
                files["package/package.json"] = json.dumps(manifest).encode()
                with self.assertRaises(ValueError):
                    guard.inspect_tgz(fixture(files), verify_sha=False)

    def test_missing_stable_export_rejected(self) -> None:
        data = dict(MANIFEST)
        data["exports"] = {".": "./dist/index.js"}
        files = dict(FILES)
        files["package/package.json"] = json.dumps(data).encode()
        with self.assertRaisesRegex(ValueError, "exports"):
            guard.inspect_tgz(fixture(files), verify_sha=False)

    def test_missing_license_body_or_css_rejected(self) -> None:
        for drop in ("package/LICENSE", "package/dist/tokens.css"):
            with self.subTest(drop=drop):
                files = dict(FILES)
                del files[drop]
                with self.assertRaises(ValueError):
                    guard.inspect_tgz(fixture(files), verify_sha=False)

    def test_first_party_branch_only_and_no_script_execution(self) -> None:
        ci = (ROOT / ".github/workflows/home-manager-import-checks.yml").read_text()
        job = ci.split("  gc-ui-foundations-provenance:", 1)[1]
        self.assertIn("github.head_ref == 'ci/gc-ui-foundations-provenance-20261108'", job)
        self.assertIn("github.event.pull_request.head.repo.full_name == 'GoreeCloud/home-manager'", job)
        self.assertIn("persist-credentials: false", job)
        self.assertIn("check_gc_ui_foundations_asset.py", job)
        self.assertNotIn("npm install", job)
        self.assertNotIn("npm run", job)


if __name__ == "__main__":
    unittest.main()
