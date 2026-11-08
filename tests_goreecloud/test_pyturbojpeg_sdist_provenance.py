"""No-network, no-execution regression tests of the pinned PyTurboJPEG source guard."""

from __future__ import annotations

from io import BytesIO
import importlib.util
from pathlib import Path
import tarfile
from unittest import mock
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/check_pyturbojpeg_sdist.py"
SPEC = importlib.util.spec_from_file_location("goreecloud_pyturbojpeg_sdist_guard", SCRIPT)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

PREFIX = "pyturbojpeg-1.8.3/"
SOURCES = {
    "setup.py": b"from setuptools import setup\nsetup(name='PyTurboJPEG')\n",
    "turbojpeg.py": b"__version__ = '1.8.3'\n",
    "LICENSE": b"MIT License\n\nCopyright (c) 2018-2026 Lilo Huang\n",
}


def tar_bytes(
    source: dict[str, bytes] | None = None,
    *,
    extra: tuple[str, bytes] | None = None,
    symlink: str | None = None,
) -> bytes:
    output = BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as tar:
        root = tarfile.TarInfo(PREFIX.rstrip("/"))
        root.type = tarfile.DIRTYPE
        tar.addfile(root)
        for name, payload in (source if source is not None else SOURCES).items():
            info = tarfile.TarInfo(PREFIX + name)
            info.size = len(payload)
            tar.addfile(info, BytesIO(payload))
        if extra:
            name, payload = extra
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, BytesIO(payload))
        if symlink:
            info = tarfile.TarInfo(PREFIX + symlink)
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)
    return output.getvalue()


class PinnedPyTurboJPEGSourceGuardTests(unittest.TestCase):
    def test_valid_synthetic_source_matches_expected_git_blobs(self) -> None:
        hashes = {name: guard.git_blob_sha1(blob) for name, blob in SOURCES.items()}
        with mock.patch.dict(guard.SOURCE_BLOBS, hashes, clear=True):
            self.assertEqual(guard.inspect_sdist(tar_bytes(), verify_digest=False), [])

    def test_unapproved_sha256_rejected_before_tar_processing(self) -> None:
        self.assertIn("SHA-256", guard.inspect_sdist(tar_bytes())[0])

    def test_setup_source_divergence_is_rejected(self) -> None:
        hashes = {name: guard.git_blob_sha1(blob) for name, blob in SOURCES.items()}
        mutated = dict(SOURCES)
        mutated["setup.py"] += b"print('unapproved payload')\n"
        with mock.patch.dict(guard.SOURCE_BLOBS, hashes, clear=True):
            result = guard.inspect_sdist(tar_bytes(mutated), verify_digest=False)
        self.assertTrue(any("source/tag identity mismatch: setup.py" in item for item in result))

    def test_traversal_and_absolute_path_rejected(self) -> None:
        for name in (PREFIX + "../outside.txt", "/tmp/escaped.txt"):
            with self.subTest(name=name):
                errors = guard.inspect_sdist(tar_bytes(extra=(name, b"bad")), verify_digest=False)
                self.assertTrue(any("unsafe" in item for item in errors))

    def test_symlink_member_rejected(self) -> None:
        self.assertTrue(any("unsafe" in item for item in guard.inspect_sdist(tar_bytes(symlink="evil"), verify_digest=False)))

    def test_required_upstream_file_missing(self) -> None:
        source = dict(SOURCES)
        del source["setup.py"]
        result = guard.inspect_sdist(tar_bytes(source), verify_digest=False)
        self.assertTrue(any("missing: setup.py" in item for item in result))

    def test_license_notice_check_rejects_wrong_text(self) -> None:
        hashes = {name: guard.git_blob_sha1(blob) for name, blob in SOURCES.items()}
        source = dict(SOURCES)
        source["LICENSE"] = b"not an MIT notice"
        with mock.patch.dict(guard.SOURCE_BLOBS, hashes, clear=True):
            result = guard.inspect_sdist(tar_bytes(source), verify_digest=False)
        self.assertTrue(any("MIT license" in item for item in result))

    def test_malformed_gzip_is_rejected(self) -> None:
        self.assertTrue(guard.inspect_sdist(b"garbage", verify_digest=False))

    def test_exact_pypi_archive_url_is_required(self) -> None:
        data = {
            "info": {"version": "1.8.3"},
            "urls": [{
                "filename": guard.FILENAME,
                "packagetype": "sdist",
                "yanked": False,
                "digests": {"sha256": guard.EXPECTED_SHA256},
                "url": "https://files.pythonhosted.org/packages/safe/pyturbojpeg-1.8.3.tar.gz",
            }],
        }
        self.assertEqual(
            guard.select_pinned_sdist(data),
            "https://files.pythonhosted.org/packages/safe/pyturbojpeg-1.8.3.tar.gz",
        )
        data["urls"][0]["digests"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            guard.select_pinned_sdist(data)

    def test_block_non_pypi_hosts_before_network_use(self) -> None:
        for url in (
            "http://files.pythonhosted.org/test",
            "https://evil.example.com/test",
            "https://username:pass@pypi.org/test",
        ):
            with self.assertRaises(ValueError):
                guard.read_bounded(url, 10)

    def test_ci_job_is_first_party_and_inert(self) -> None:
        workflow = (ROOT / ".github/workflows/home-manager-import-checks.yml").read_text()
        self.assertIn("pyturbojpeg-sdist-provenance:", workflow)
        self.assertIn("github.head_ref == 'ci/pyturbojpeg-sdist-provenance-20261108'", workflow)
        self.assertIn("python3 tools/check_pyturbojpeg_sdist.py", workflow)


if __name__ == "__main__":
    unittest.main()
