"""Offline source-only Bluetooth recovery dependency invariant tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/check_bluetooth_dependency_invariants.py"
SPEC = importlib.util.spec_from_file_location("home_manager_bluetooth_invariants", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class BluetoothRecoveryPinGuardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.sources = {
            "homeassistant/components/bluetooth/manifest.json": json.dumps({
                "domain": "bluetooth",
                "loggers": ["bluetooth_auto_recovery", "habluetooth"],
                "requirements": sorted(guard.MANIFEST_PINS),
            }),
            "homeassistant/package_constraints.txt":
                "\n".join(sorted(guard.CONSTRAINT_PINS)) + "\n",
            "requirements.txt": "home-assistant-bluetooth==2.0.0\n",
            "homeassistant/components/bluetooth/__init__.py":
                "from habluetooth import (\n)\n\nasync def async_setup(hass, config):\n    return True\n",
        }
        for relative, source in self.sources.items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source)

    def change(self, relative, old, new):
        target = self.root / relative
        text = target.read_text()
        self.assertIn(old, text)
        target.write_text(text.replace(old, new))

    def test_only_declared_source_pin_edges_are_checked_without_runtime_claims(self):
        result = guard.audit(self.root)
        self.assertEqual(result["upstream_recovery_package"], "bluetooth-auto-recovery==1.6.4")
        self.assertFalse(result["release_ready"])
        self.assertFalse(result["bluetooth_device_operations_performed"])
        self.assertFalse(result["license_compatibility_approved"])
        self.assertFalse(result["native_recovery_privilege_review_complete"])

    def test_bluetooth_manifest_pin_change_requires_review(self):
        self.change("homeassistant/components/bluetooth/manifest.json",
                    "bluetooth-auto-recovery==1.6.4", "bluetooth-auto-recovery==9.9.9")
        with self.assertRaisesRegex(ValueError, "security review"):
            guard.audit(self.root)

    def test_constraint_pin_drift_requires_review(self):
        self.change("homeassistant/package_constraints.txt",
                    "habluetooth==7.1.2", "habluetooth==7.2.0")
        with self.assertRaisesRegex(ValueError, "constraints changed"):
            guard.audit(self.root)

    def test_direct_bluetooth_package_pin_drift_requires_review(self):
        self.change("requirements.txt",
                    "home-assistant-bluetooth==2.0.0", "home-assistant-bluetooth==9.0.0")
        with self.assertRaisesRegex(ValueError, "direct Home Assistant"):
            guard.audit(self.root)

    def test_missing_recovery_logger_reference_is_detected(self):
        self.change("homeassistant/components/bluetooth/manifest.json",
                    "bluetooth_auto_recovery", "unknown_recovery")
        with self.assertRaisesRegex(ValueError, "logger/reference"):
            guard.audit(self.root)

    def test_symlinked_manifest_refused_without_following(self):
        manifest = self.root / "homeassistant/components/bluetooth/manifest.json"
        manifest.unlink()
        manifest.symlink_to(self.root / "requirements.txt")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            guard.audit(self.root)

    def test_duplicate_constraint_does_not_pass(self):
        constraint = self.root / "homeassistant/package_constraints.txt"
        constraint.write_text(constraint.read_text() + "habluetooth==7.1.2\n")
        with self.assertRaisesRegex(ValueError, "constraints changed"):
            guard.audit(self.root)

    def test_audit_source_does_not_import_or_execute_bluetooth_or_pyric(self):
        content = SCRIPT.read_text()
        self.assertNotIn("import bluetooth_auto_recovery", content)
        self.assertNotIn("import PyRIC", content)
        self.assertNotIn("import pyric", content)
        self.assertNotIn("subprocess", content)
        self.assertNotIn("socket.", content)
        self.assertNotIn("rfkill", content.lower())
        self.assertNotIn("ioctl", content.lower())


if __name__ == "__main__":
    unittest.main()
