"""Pure mock-only server-side state minimization regression tests.

NO real Home Assistant imports, network, tokens, physical devices, or services.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/home_manager_privacy_projection.py"
SPEC = importlib.util.spec_from_file_location("home_manager_privacy_projection", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
privacy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(privacy)


class FakeState:
    entity_id = "light.demo_lamp"
    state = "on"

    @property
    def attributes(self):
        raise AssertionError("private attributes must never be accessed")

    @property
    def as_dict_json(self):
        raise AssertionError("full Home Assistant state must not be serialized")

    @property
    def context(self):
        raise AssertionError("private context must never be accessed")


class FakeStates:
    def __init__(self, state=FakeState()):
        self.state = state
        self.lookups = []

    def get(self, entity_id):
        self.lookups.append(entity_id)
        return self.state

    def async_all(self):
        raise AssertionError("bulk state enumeration is forbidden")


class FakePermissions:
    def __init__(self, allowed=True, fail=False):
        self.allowed = allowed
        self.fail = fail
        self.checks = []

    def check_entity(self, entity_id, policy):
        self.checks.append((entity_id, policy))
        if self.fail:
            raise RuntimeError("private user diagnostic must not leak")
        return self.allowed


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.states = FakeStates()
        self.permissions = FakePermissions()
        self.hass = SimpleNamespace(states=self.states)
        self.user = SimpleNamespace(permissions=self.permissions)
        self.consent = True

    def run_projection(self, **overrides):
        params = {
            "entity_id": "light.demo_lamp",
            "consented_entity_ids": ["light.demo_lamp"],
            "consent_is_active": lambda: self.consent,
            "user": self.user,
            "hass": self.hass,
        }
        params.update(overrides)
        return privacy.project_authorized_entity(**params)

    def test_source_const_and_permission_order_match_imported_core(self):
        constants = (ROOT / "homeassistant/auth/permissions/const.py").read_text()
        source = (ROOT / "homeassistant/components/api/__init__.py").read_text()
        self.assertIn('POLICY_READ = "read"', constants)
        self.assertIn('url = "/api/states/{entity_id}"', source)
        start = source.index("class APIEntityStateView(")
        getter = source.index("    def get(self, request:", start)
        perm = source.index("user.permissions.check_entity(entity_id, POLICY_READ)", getter)
        lookup = source.index("hass.states.get(entity_id)", getter)
        self.assertLess(perm, lookup)
        self.assertEqual(privacy.POLICY_READ, "read")

    def test_authorized_fixture_projects_only_two_scalar_fields(self):
        payload = self.run_projection()
        self.assertEqual(json.loads(payload), {"entity_id": "light.demo_lamp", "state": "on"})
        self.assertEqual(self.permissions.checks, [("light.demo_lamp", "read")])
        self.assertEqual(self.states.lookups, ["light.demo_lamp"])
        self.assertLessEqual(len(payload), privacy.MAX_RESPONSE_BYTES)
        for leak in (b"attributes", b"timestamp", b"context", b"location", b"user"):
            self.assertNotIn(leak, payload)

    def test_consent_denial_refuses_before_permission_and_state_lookup(self):
        self.consent = False
        with self.assertRaises(privacy.EntityNotVisible):
            self.run_projection()
        self.assertEqual(self.permissions.checks, [])
        self.assertEqual(self.states.lookups, [])

    def test_unconsented_id_refused_without_discovery_or_permission_call(self):
        with self.assertRaises(privacy.EntityNotVisible):
            self.run_projection(entity_id="person.demo_person")
        self.assertEqual(self.permissions.checks, [])
        self.assertEqual(self.states.lookups, [])

    def test_unauthorized_user_denied_before_state_lookup(self):
        self.permissions.allowed = False
        with self.assertRaisesRegex(privacy.EntityNotVisible, "^Entity not available$"):
            self.run_projection()
        self.assertEqual(self.permissions.checks, [("light.demo_lamp", "read")])
        self.assertEqual(self.states.lookups, [])

    def test_missing_and_unauthorized_have_same_error_and_no_sensitive_detail(self):
        self.permissions.allowed = False
        with self.assertRaises(privacy.EntityNotVisible) as denied:
            self.run_projection()
        self.permissions.allowed = True
        self.states.state = None
        with self.assertRaises(privacy.EntityNotVisible) as missing:
            self.run_projection()
        self.assertEqual(str(denied.exception), str(missing.exception))

    def test_consent_revocation_between_read_and_serialization_fails_closed(self):
        calls = []
        def active():
            calls.append(True)
            return len(calls) < 2
        with self.assertRaises(privacy.EntityNotVisible):
            self.run_projection(consent_is_active=active)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.states.lookups, ["light.demo_lamp"])

    def test_invalid_entity_ids_and_scope_rejected_before_any_sensitive_access(self):
        for candidate in ("", "person.demo/person", "../etc/passwd", "light.", "light.a?x=1",
                          "light.a%2Fbad", "LIGHT.lamp", "light.a\nbad", "x" * 110, None):
            with self.subTest(candidate=candidate):
                with self.assertRaises(privacy.EntityNotVisible):
                    self.run_projection(entity_id=candidate)
        for ids in ([], ["light.demo_lamp", "light.demo_lamp"],
                    ["light.demo_lamp", "../../all"],
                    [f"light.demo_{i}" for i in range(33)], "light.demo_lamp", None):
            with self.subTest(ids=ids):
                with self.assertRaises(privacy.EntityNotVisible):
                    self.run_projection(consented_entity_ids=ids)
        self.assertEqual(self.permissions.checks, [])
        self.assertEqual(self.states.lookups, [])

    def test_mismatched_state_id_and_malformed_state_refused_without_values(self):
        for state in (SimpleNamespace(entity_id="person.private", state="home"),
                      SimpleNamespace(entity_id="light.demo_lamp", state="on\nlocation"),
                      SimpleNamespace(entity_id="light.demo_lamp", state="x" * 121),
                      SimpleNamespace(entity_id="light.demo_lamp", state=24)):
            self.states.state = state
            with self.subTest(state=state):
                with self.assertRaises(privacy.EntityNotVisible):
                    self.run_projection()

    def test_provider_exception_strings_never_escape(self):
        self.permissions.fail = True
        with self.assertRaisesRegex(privacy.EntityNotVisible, "^Entity not available$") as error:
            self.run_projection()
        self.assertNotIn("private user diagnostic", str(error.exception))

    def test_no_io_transport_auth_or_ha_runtime_imports(self):
        source = SCRIPT.read_text()
        self.assertNotIn("from homeassistant ", source)
        self.assertNotIn("import homeassistant", source)
        for word in ("requests.", "urllib.request", "socket.", "async_all(", ".as_dict_json",
                     "localStorage", "Authorization:", "print("):
            if word in (".as_dict_json", "async_all("):
                # Negative references in comments/docstrings are intentional.
                continue
            self.assertNotIn(word, source)
        self.assertNotIn("create_route(", source)
        self.assertNotIn("register_view(", source)


if __name__ == "__main__":
    unittest.main()
