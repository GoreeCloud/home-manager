"""Read-only CI policy tests for the experimental Linux ABI3 audio probe.

These tests never download, install, import or execute third-party audio code.
"""

from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/home-manager-import-checks.yml"


class AssistAbi3ProbePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.probe = cls.workflow.split("  assist-audio-abi3-probe:", maxsplit=1)[1]

    def test_probe_is_scoped_to_review_branch(self) -> None:
        self.assertIn("github.event.pull_request.head.repo.full_name == 'GoreeCloud/home-manager'", self.probe)
        self.assertIn("github.head_ref == 'feat/assist-abi3-candidate-smoke-20261108'", self.probe)
        self.assertIn("persist-credentials: false", self.probe)

    def test_exact_pinned_versions_and_sha256(self) -> None:
        for item in (
            "pymicro-vad==2.1.0",
            "pyspeex-noise==2.0.1",
            "a99894b0eb58e713aceff2503ba371e3816801a30b3c60443bd39d22b8699e64",
            "bbcc365556bd184ab3da17276dbfadb21485dcd013496889006eb31ffb341c06",
        ):
            with self.subTest(item=item):
                self.assertIn(item, self.probe)

    def test_only_download_binary_wheels_then_install_offline(self) -> None:
        self.assertIn("--isolated download --no-deps --only-binary=:all:", self.probe)
        self.assertIn("--no-index --no-deps --no-compile", self.probe)
        self.assertIn("timeout 25s", self.probe)
        self.assertNotIn("pip install -r requirements.txt", self.probe)

    def test_bridge_prevents_bad_pcm_length_before_native_calls(self) -> None:
        bridge = (ROOT / "homeassistant/components/assist_pipeline/audio_compat.py").read_text()
        self.assertIn("_require_frame(audio)", bridge)
        self.assertIn("if len(audio) != _FRAME_BYTES:", bridge)
        self.assertIn("_require_processed_frame", bridge)
        self.assertIn("silent_10ms = bytes(320)", self.probe)

    def test_upstream_generated_pins_not_modified(self) -> None:
        for filename in (
            "requirements.txt",
            "requirements_all.txt",
            "homeassistant/package_constraints.txt",
            "homeassistant/components/assist_pipeline/manifest.json",
        ):
            with self.subTest(path=filename):
                text = (ROOT / filename).read_text(encoding="utf-8")
                self.assertIn("pymicro-vad==1.0.1", text)
                self.assertIn("pyspeex-noise==1.0.2", text)


if __name__ == "__main__":
    unittest.main()
