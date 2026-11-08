"""No-network, no-execution regression tests for pinned PyRIC source preflight."""

from __future__ import annotations

from io import BytesIO
import importlib.util
from pathlib import Path
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/inspect_pyric_sdist.py"
SPEC = importlib.util.spec_from_file_location("home_manager_pyric_source", SCRIPT)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)
ROOTDIR = "PyRIC-0.1.6.3"
FIXTURE = {
    "setup.py": b"import pyric\nfrom setuptools import setup\nsetup(name='PyRIC')\n",
    "pyric/__init__.py": b"version = '0.1.6.3'\n",
    "LICENSE": b"GNU General Public License version 3\nCopyright Dale Patterson\n",
}


def make_tar(
    files: dict[str, bytes] | None = None,
    *,
    extra: tuple[str, bytes] | None = None,
    link: str | None = None,
) -> bytes:
    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        directory = tarfile.TarInfo(ROOTDIR)
        directory.type = tarfile.DIRTYPE
        tf.addfile(directory)
        for name, data in (FIXTURE if files is None else files).items():
            info = tarfile.TarInfo(ROOTDIR + "/" + name)
            info.size = len(data)
            tf.addfile(info, BytesIO(data))
        if extra:
            name, data = extra
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, BytesIO(data))
        if link:
            info = tarfile.TarInfo(ROOTDIR + "/" + link)
            info.type = tarfile.SYMTYPE
            info.linkname = "/dev/net/tun"
            tf.addfile(info)
    return buf.getvalue()


class PyRICSourcePreflightTests(unittest.TestCase):
    def test_fixture_is_inert_and_does_not_accept_release(self) -> None:
        data = make_tar()
        result = guard.inspect_archive(data, check_hash=False)
        self.assertTrue(result["source_only"])
        self.assertTrue(result["setup_imports_pyric"])
        self.assertTrue(result["GPL_source_notice"])
        self.assertFalse(result["release_ready"])
        self.assertFalse(result["matching_0_1_6_3_git_tag_verified"])
        self.assertFalse(result["source_executed"])
        self.assertFalse(result["device_accessed"])

    def test_unverified_pypi_checksum_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            guard.inspect_archive(make_tar())

    def test_bad_member_paths_cannot_escape(self) -> None:
        for name in (ROOTDIR + "/../outside.py", "/tmp/injected.py", ROOTDIR + "\\windows.py"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    guard.inspect_archive(make_tar(extra=(name, b"bad")), check_hash=False)

    def test_symlink_member_never_passes(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe"):
            guard.inspect_archive(make_tar(link="danger"), check_hash=False)

    def test_missing_license_or_init_is_rejected(self) -> None:
        for required in ("LICENSE", "pyric/__init__.py", "setup.py"):
            with self.subTest(required=required):
                partial = dict(FIXTURE)
                del partial[required]
                with self.assertRaisesRegex(ValueError, "missing"):
                    guard.inspect_archive(make_tar(partial), check_hash=False)

    def test_non_gpl_source_notice_is_rejected(self) -> None:
        files = dict(FIXTURE)
        files["LICENSE"] = b"Unspecified rights"
        with self.assertRaisesRegex(ValueError, "GPL attribution"):
            guard.inspect_archive(make_tar(files), check_hash=False)

    def test_unexpected_sdist_release_hash_is_rejected(self) -> None:
        item = {
            "info": {"version": "0.1.6.3"},
            "urls": [{
                "filename": guard.FILENAME,
                "packagetype": "sdist",
                "digests": {"sha256": guard.EXPECTED_SHA256},
                "yanked": False,
                "url": "https://files.pythonhosted.org/packages/pinned/PyRIC-0.1.6.3.tar.gz",
            }],
        }
        self.assertEqual(guard.select_release(item), item["urls"][0]["url"])
        item["urls"][0]["digests"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "mismatch"):
            guard.select_release(item)

    def test_disallowed_hosts_are_never_fetched(self) -> None:
        for url in ("http://pypi.org/a", "https://evil.example.com/a", "https://user:pass@pypi.org/a"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    guard.read_bounded(url, 100)

    def test_branch_restriction_and_no_source_execution(self) -> None:
        workflow = (ROOT / ".github/workflows/home-manager-import-checks.yml").read_text(encoding="utf-8")
        self.assertIn("pyric-source-provenance:", workflow)
        self.assertIn("github.head_ref == 'ci/pyric-source-provenance-20261108'", workflow)
        self.assertIn("python tools/inspect_pyric_sdist.py", workflow)
        source = SCRIPT.read_text(encoding="utf-8")
        for marker in ("tarfile.open(", "archive.extractfile(", "matching_0_1_6_3_git_tag_verified", "GPL_source_notice"):
            self.assertIn(marker, source)
        self.assertNotIn("extractall(", source)


if __name__ == "__main__":
    unittest.main()
