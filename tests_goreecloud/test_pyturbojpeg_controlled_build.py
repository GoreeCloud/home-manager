"""Synthetic, no-install validation of controlled PyTurboJPEG source staging and wheel checks."""

from __future__ import annotations

from io import BytesIO
import hashlib
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_pyturbojpeg_sdist as source_guard  # noqa: E402
import prepare_pyturbojpeg_wheel_source as staging  # noqa: E402
import check_pyturbojpeg_built_wheel as wheel_guard  # noqa: E402

FILES = {
    "setup.py": b"from setuptools import setup\nsetup(name='PyTurboJPEG')\n",
    "turbojpeg.py": b"__version__ = '1.8.3'\n",
    "README.md": b"# PyTurboJPEG\nSynthetic fixture only.\n",
    "LICENSE": b"MIT License\n\nCopyright (c) 2018-2026 Lilo Huang\n",
}
WHEEL_PREFIX = "pyturbojpeg-1.8.3.dist-info/"


def fake_sdist(source: dict[str, bytes] | None = None) -> bytes:
    stream = BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as tar:
        info = tarfile.TarInfo("pyturbojpeg-1.8.3")
        info.type = tarfile.DIRTYPE
        tar.addfile(info)
        for name, data in (source if source is not None else FILES).items():
            info = tarfile.TarInfo("pyturbojpeg-1.8.3/" + name)
            info.size = len(data)
            tar.addfile(info, BytesIO(data))
    return stream.getvalue()


def make_wheel(path: Path, modifications: dict[str, bytes | None] | None = None) -> None:
    contents = {
        "turbojpeg.py": FILES["turbojpeg.py"],
        WHEEL_PREFIX + "METADATA": b"Metadata-Version: 2.4\nName: PyTurboJPEG\nVersion: 1.8.3\nLicense: MIT\n",
        WHEEL_PREFIX + "WHEEL": b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        WHEEL_PREFIX + "RECORD": b"synthetic fixture\n",
        WHEEL_PREFIX + "licenses/LICENSE": FILES["LICENSE"],
    }
    for key, value in (modifications or {}).items():
        if value is None:
            contents.pop(key, None)
        else:
            contents[key] = value
    with ZipFile(path, "w") as archive:
        for name, data in contents.items():
            archive.writestr(name, data)


class PyTurboJPEGBuildGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.wheel = self.root / "pyturbojpeg-1.8.3-py3-none-any.whl"

    def guarded_source(self, body: bytes):
        hashes = {k: source_guard.git_blob_sha1(v) for k, v in FILES.items() if k in source_guard.SOURCE_BLOBS}
        return mock.patch.multiple(
            source_guard,
            EXPECTED_SHA256=hashlib.sha256(body).hexdigest(),
            SOURCE_BLOBS=hashes,
        )

    def test_stage_only_four_verified_source_files(self) -> None:
        tar = fake_sdist()
        destination = self.root / "stage"
        with self.guarded_source(tar):
            staging.stage_verified_source(tar, destination)
        self.assertEqual({p.name for p in destination.iterdir()}, set(staging.SOURCE_FILES))
        for name, contents in FILES.items():
            self.assertEqual((destination / name).read_bytes(), contents)

    def test_incorrect_source_never_creates_output_directory(self) -> None:
        location = self.root / "stage"
        with self.assertRaises(ValueError):
            staging.stage_verified_source(b"bad data", location)
        self.assertFalse(location.exists())

    def test_existing_source_directory_is_not_overwritten(self) -> None:
        body = fake_sdist()
        location = self.root / "stage"
        location.mkdir()
        with self.guarded_source(body):
            with self.assertRaisesRegex(ValueError, "new directory"):
                staging.stage_verified_source(body, location)

    def test_missing_readme_rejected_before_staging(self) -> None:
        source = dict(FILES)
        del source["README.md"]
        data = fake_sdist(source)
        with self.guarded_source(data):
            with self.assertRaises((KeyError, ValueError)):
                staging.stage_verified_source(data, self.root / "stage")

    def test_synthetic_universal_wheel_accepted(self) -> None:
        make_wheel(self.wheel)
        with mock.patch.dict(source_guard.SOURCE_BLOBS, {
            "turbojpeg.py": source_guard.git_blob_sha1(FILES["turbojpeg.py"]),
            "LICENSE": source_guard.git_blob_sha1(FILES["LICENSE"]),
        }):
            self.assertEqual(wheel_guard.inspect(self.wheel), [])

    def test_native_library_member_is_rejected(self) -> None:
        make_wheel(self.wheel, {"unexpected.pyd": b"opaque"})
        self.assertIn("native", " ".join(wheel_guard.inspect(self.wheel)))

    def test_inaccurate_version_is_rejected(self) -> None:
        make_wheel(self.wheel, {WHEEL_PREFIX + "METADATA": b"Name: PyTurboJPEG\nVersion: 2.0.0\nLicense: MIT\n"})
        self.assertIn("version", " ".join(wheel_guard.inspect(self.wheel)))

    def test_malformed_metadata_and_license_cannot_pass(self) -> None:
        make_wheel(self.wheel, {WHEEL_PREFIX + "licenses/LICENSE": None})
        self.assertIn("license", " ".join(wheel_guard.inspect(self.wheel)))

    def test_unexpected_wheel_filename_rejected(self) -> None:
        other = self.root / "PyTurboJPEG-unpinned.whl"
        make_wheel(other)
        self.assertTrue(wheel_guard.inspect(other))

    def test_reviewed_workflow_scopes_execution_and_hashes_backend(self) -> None:
        text = (ROOT / ".github/workflows/home-manager-import-checks.yml").read_text()
        block = text.split("  pyturbojpeg-controlled-wheel:", 1)[1]
        self.assertIn("github.head_ref == 'ci/pyturbojpeg-controlled-wheel-20261108'", block)
        self.assertIn("persist-credentials: false", block)
        self.assertIn("51a52592b3b99e102b609654876bd65f19f999935166d1352678931132b0c670", block)
        self.assertIn("--no-build-isolation --no-deps", block)
        self.assertIn("--no-index --no-deps", block)
        self.assertIn("check_pyturbojpeg_built_wheel.py", block)


if __name__ == "__main__":
    unittest.main()
