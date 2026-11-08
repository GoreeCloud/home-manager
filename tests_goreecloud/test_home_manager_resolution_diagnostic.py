"""Offline negative-path checks of Core resolver's explicit blocked outcome."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/assess_home_manager_resolution_diagnostic.py"
SPEC = importlib.util.spec_from_file_location("home_manager_candidate_diagnostic", SCRIPT)
assert SPEC and SPEC.loader
assessor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(assessor)

PYRIC_ERROR = """error: No solution found when resolving dependencies
cause: Because pyric==0.1.6.3 has no usable wheels and only pyric<=0.1.6.3 is available,
and because bluetooth-auto-recovery>=1.6.4 depends on pyric>=0.1.6.3
and habluetooth>=7.1.2 depends on bluetooth-auto-recovery==1.6.4
and home-assistant-bluetooth>=2.0.0 depends on habluetooth==7.1.2
hint: source builds disabled under --no-build.
"""


class CoreResolutionDiagnosticTests(unittest.TestCase):
    def test_expected_pyric_failure_is_diagnostic_only(self) -> None:
        result = assessor.classify(1, PYRIC_ERROR, None)
        self.assertEqual(result["status"], "blocked_source_only_pyric")
        self.assertIs(result["release_ready"], False)
        self.assertIs(result["full_dependency_graph_solved"], False)
        self.assertEqual(len(result["dependency_chain"]), 4)

    def test_unsupported_errors_are_not_accepted(self) -> None:
        for exit_code, message in (
            (1, "error: network timed out"),
            (1, "No solution found when resolving dependencies\nother-package has no usable wheels"),
            (124, PYRIC_ERROR),
            (2, PYRIC_ERROR),
        ):
            with self.subTest(status=exit_code, log=message[:40]):
                with self.assertRaises(ValueError):
                    assessor.classify(exit_code, message, None)

    def test_diagnostic_requires_all_dependency_chain_evidence(self) -> None:
        for marker in assessor.KNOWN_PYRIC_MARKERS:
            with self.subTest(marker=marker):
                with self.assertRaises(ValueError):
                    assessor.classify(1, PYRIC_ERROR.replace(marker, ""), None)

    def test_success_requires_both_reviewed_audio_candidates(self) -> None:
        lines = [f"fixture-{i}==1.0.0" for i in range(57)]
        lines += ["pymicro-vad==2.1.0", "pyspeex-noise==2.0.1", "pyturbojpeg==1.8.3"]
        success = "\n".join(lines)
        result = assessor.classify(0, "", success)
        self.assertEqual(result["status"], "candidate_metadata_solved")
        self.assertIs(result["release_ready"], False)
        self.assertGreaterEqual(result["resolved_exact_pins"], 56)

        with self.assertRaises(ValueError):
            assessor.classify(0, "", success.replace("pymicro-vad==2.1.0", "pymicro-vad==1.0.1"))
        with self.assertRaises(ValueError):
            assessor.classify(0, "", success.replace("pyturbojpeg==1.8.3", "pyturbojpeg==2.0.0"))

    def test_missing_lock_is_never_marked_successful(self) -> None:
        with self.assertRaises(ValueError):
            assessor.classify(0, "", None)

    def test_first_party_review_scope_and_no_build_cli_retained(self) -> None:
        workflow = (ROOT / ".github/workflows/home-manager-import-checks.yml").read_text(encoding="utf-8")
        job = workflow.split("  core-resolution-candidate-uv:", 1)[1]
        self.assertIn("github.event.pull_request.head.repo.full_name == 'GoreeCloud/home-manager'", job)
        self.assertIn("github.head_ref == 'ci/core-resolution-candidate-uv-20261108'", job)
        self.assertIn("--no-config --no-cache --no-build", job)
        self.assertIn("assess_home_manager_resolution_diagnostic.py", job)
        self.assertIn("solver_status=$?", job)
        self.assertIn("PYRIC", SCRIPT.read_text().upper())


if __name__ == "__main__":
    unittest.main()
