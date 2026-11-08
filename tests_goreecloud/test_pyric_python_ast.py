"""No-network, no-execution tests for exact PyRIC Python source AST inspection."""

from __future__ import annotations

import ast
from io import BytesIO
from pathlib import Path
import sys
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audit_pyric_python_ast as scanner  # noqa: E402

ROOTDIR = "PyRIC-0.1.6.3"


def source_archive(*, malformed: bool = False, extra: tuple[str, bytes] | None = None) -> bytes:
    sources = {
        "setup.py": b"import pyric\nfrom setuptools import setup\nsetup(name='PyRIC')\n",
        "pyric/__init__.py": b"version = '0.1.6.3'\n",
        "LICENSE": b"GNU General Public License version 3\nCopyright Dale Patterson\n",
        "pyric/check.py": b"import socket\nimport fcntl\nvalue = eval('1+1')\n",
    }
    for i in range(8):
        sources[f"pyric/module_{i}.py"] = b"value = 1\n"
    if malformed:
        sources["pyric/module_0.py"] = b"print 'legacy syntax'\n"
    if extra:
        sources[extra[0]] = extra[1]
    stream = BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as tf:
        folder = tarfile.TarInfo(ROOTDIR)
        folder.type = tarfile.DIRTYPE
        tf.addfile(folder)
        for name, body in sources.items():
            member = tarfile.TarInfo(ROOTDIR + "/" + name)
            member.size = len(body)
            tf.addfile(member, BytesIO(body))
    return stream.getvalue()


class PyRICPythonASTTests(unittest.TestCase):
    def test_inert_source_parser_finds_sensitive_imports_and_dynamic_syntax(self) -> None:
        result = scanner.analyze_archive(source_archive(), check_hash=False)
        self.assertGreaterEqual(result["python_files_parsed_or_attempted"], 8)
        self.assertEqual(result["python_syntax_errors"], [])
        self.assertIn("socket", result["sensitive_module_import_names_observed"])
        self.assertIn("fcntl", result["sensitive_module_import_names_observed"])
        self.assertEqual(result["dynamic_call_syntax_counts"]["eval"], 1)
        self.assertIs(result["source_executed"], False)
        self.assertIs(result["wireless_devices_accessed"], False)
        self.assertIs(result["runtime_compatible_verified"], False)
        self.assertIs(result["release_ready"], False)
        self.assertIs(result["upstream_0_1_6_3_tag_verified"], False)

    def test_old_python2_print_statement_is_detected_not_executed(self) -> None:
        result = scanner.analyze_archive(source_archive(malformed=True), check_hash=False)
        self.assertIn("pyric/module_0.py", result["python_syntax_errors"])
        self.assertIs(result["source_executed"], False)

    def test_sensitive_call_alias_mapping_is_static_and_source_only(self) -> None:
        tree = ast.parse(
            "import socket as sock\n"
            "from fcntl import ioctl as control\n"
            "import subprocess as process\n"
            "import os\n"
            "sock.socket()\n"
            "control(0, 0)\n"
            "process.Popen(['true'])\n"
            "os.seteuid(0)\n"
            "os.chmod('file', 0o700)\n"
        )
        found = scanner.inspect_static_call_sites(tree)
        self.assertEqual(set(found), {
            "socket.socket", "fcntl.ioctl", "subprocess.Popen",
            "os.seteuid", "os.chmod",
        })
        self.assertEqual(found["fcntl.ioctl"], [6])
        self.assertEqual(found["socket.socket"], [5])

    def test_unrelated_calls_do_not_create_permission_claims(self) -> None:
        tree = ast.parse("import json\njson.dumps({'socket': 'x'})\nfoo.socket()\n")
        self.assertEqual(scanner.inspect_static_call_sites(tree), {})

    def test_risk_label_is_not_a_runtime_approval(self) -> None:
        tree = ast.parse("import socket\nsocket.socket()\n")
        self.assertIn("socket.socket", scanner.inspect_static_call_sites(tree))
        source = (ROOT / "tools/audit_pyric_python_ast.py").read_text(encoding="utf-8")
        self.assertIn('"runtime_compatible_verified": False', source)
        self.assertIn('"release_ready": False', source)
        self.assertIn("manual review required", source)

    def test_archive_source_path_traversal_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe"):
            scanner.analyze_archive(source_archive(extra=("../evil.py", b"print('bad')")), check_hash=False)

    def test_missing_gpl_notice_is_rejected_before_parsing(self) -> None:
        archive = source_archive(extra=("EXTRA.py", b"value = 123\n"))
        with self.assertRaisesRegex(ValueError, "checksum"):
            scanner.analyze_archive(archive)

    def test_no_python_bytecode_or_wireless_operations_exist_in_auditor(self) -> None:
        source = (ROOT / "tools/audit_pyric_python_ast.py").read_text(encoding="utf-8")
        self.assertIn("ast.parse(", source)
        self.assertIn("tokenize.detect_encoding(", source)
        self.assertNotIn("exec(compile(", source)
        self.assertNotIn("extractall(", source)
        self.assertNotIn("subprocess.run(", source)
        self.assertNotIn("socket.socket(", source)

    def test_hosted_job_scoped_and_no_pyric_imports(self) -> None:
        workflow = (ROOT / ".github/workflows/home-manager-import-checks.yml").read_text(encoding="utf-8")
        job = workflow.split("  pyric-static-python-compat:", 1)[1]
        self.assertIn("github.head_ref == 'ci/pyric-static-python-compat-20261108'", job)
        self.assertIn("github.event.pull_request.head.repo.full_name == 'GoreeCloud/home-manager'", job)
        self.assertIn("persist-credentials: false", job)
        self.assertIn("python tools/audit_pyric_python_ast.py", job)
        self.assertIn("github.head_ref == 'ci/pyric-static-capability-map-20261108'", job)
        self.assertNotIn("pip install pyric", job)


if __name__ == "__main__":
    unittest.main()
