"""Static, no-native-execution tests for the disposable JPEG runtime candidate."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest import mock
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/smoke_pyturbojpeg_jpeg.py"
SPEC = importlib.util.spec_from_file_location("home_manager_jpeg_synthetic_smoke", SCRIPT)
assert SPEC and SPEC.loader
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


class SyntheticJPEGRuntimePolicyTests(unittest.TestCase):
    def test_script_is_inert_without_explicit_ci_environment(self) -> None:
        with mock.patch.dict(os.environ, {"GOREECLOUD_SYNTHETIC_CODEC_CI": ""}):
            self.assertEqual(smoke.main(), 2)

    def test_script_uses_only_bounded_synthetic_pixels(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("np.empty((48, 64, 3)", source)
        self.assertIn("codec.decode_header(jpeg)", source)
        self.assertIn("codec.scale_with_quality(jpeg, scaling_factor=(1, 2)", source)
        self.assertIn("scaled_header[:2] == (32, 24)", source)
        self.assertIn("decoded.shape == (24, 32, 3)", source)
        self.assertNotIn("cv2.VideoCapture", source)
        self.assertNotIn("requests.get", source)

    def test_pinned_versions_are_checked_at_execution(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('metadata.version("PyTurboJPEG") == "1.8.3"', source)
        self.assertIn('metadata.version("numpy") == "2.3.2"', source)
        self.assertIn("sys.version_info[:3] != (3, 14, 10)", source)

    def test_runtime_job_is_first_party_and_explicitly_scoped(self) -> None:
        workflow = (ROOT / ".github/workflows/home-manager-import-checks.yml").read_text(encoding="utf-8")
        section = workflow.split("  pyturbojpeg-controlled-wheel:", 1)[1]
        self.assertIn("github.event.pull_request.head.repo.full_name == 'GoreeCloud/home-manager'", section)
        self.assertIn("github.head_ref == 'ci/pyturbojpeg-synthetic-runtime-20261108'", section)
        self.assertIn("GOREECLOUD_SYNTHETIC_CODEC_CI=1", section)
        self.assertIn("timeout 30s", section)
        self.assertIn("persist-credentials: false", section)

    def test_numpy_artifact_and_libjpeg_library_are_pinned(self) -> None:
        workflow = (ROOT / ".github/workflows/home-manager-import-checks.yml").read_text()
        self.assertIn("numpy==2.3.2", workflow)
        self.assertIn("fed5527c4cf10f16c6d0b6bee1f89958bccb0ad2522c8cadc2efd318bcd545f5", workflow)
        self.assertIn("libturbojpeg", workflow)
        self.assertIn("1:2.1.5-", workflow)
        self.assertIn("--no-index --no-deps --no-compile", workflow)

    def test_imported_pins_remain_unchanged(self) -> None:
        for name in (
            "requirements.txt",
            "requirements_all.txt",
            "homeassistant/package_constraints.txt",
            "homeassistant/components/camera/manifest.json",
            "homeassistant/components/stream/manifest.json",
        ):
            with self.subTest(name=name):
                source = (ROOT / name).read_text(encoding="utf-8")
                self.assertIn("PyTurboJPEG==1.8.3", source)


if __name__ == "__main__":
    unittest.main()
