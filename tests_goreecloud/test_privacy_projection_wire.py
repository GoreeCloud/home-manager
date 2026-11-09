"""Disposable 127.0.0.1-only HTTP wire test for the *synthetic* privacy projector.

This test defines a fake local HTTP server solely to confirm what bytes a
future response boundary would send. No real Home Assistant imports, accounts,
devices, credentials, external network calls, routes or deployment.
"""

from __future__ import annotations

from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, HTTPServer
import importlib.util
import json
from pathlib import Path
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/home_manager_privacy_projection.py"
SPEC = importlib.util.spec_from_file_location("hm_privacy_projection_wire", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
privacy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(privacy)

ALLOWED = ("light.demo_lamp", "sensor.demo_missing", "person.demo_private")
BASE = "/_synthetic/entity/"


class FakeState:
    entity_id = "light.demo_lamp"
    state = "on"

    @property
    def attributes(self):
        raise AssertionError("private attributes must never be serialized")

    @property
    def as_dict_json(self):
        raise AssertionError("full state serialization is forbidden")

    @property
    def context(self):
        raise AssertionError("private context must never be read")


class FakePermissions:
    def check_entity(self, entity_id, policy):
        return policy == "read" and entity_id != "person.demo_private"


class FakeStore:
    def get(self, entity_id):
        return FakeState() if entity_id == "light.demo_lamp" else None

    def async_all(self):
        raise AssertionError("full state inventory must never be read")


class FakeUser:
    permissions = FakePermissions()


class FakeHass:
    states = FakeStore()


class LocalOnlyHandler(BaseHTTPRequestHandler):
    """This intentionally never registers with Home Assistant or a real app."""

    def log_message(self, *unused):
        # No request identifiers, state values, or token material in logs.
        return

    def respond(self, status, payload):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if not self.path.startswith(BASE):
            self.respond(404, b'{"error":"not available"}')
            return
        entity_id = self.path[len(BASE):]
        try:
            payload = privacy.project_authorized_entity(
                entity_id=entity_id,
                consented_entity_ids=ALLOWED,
                consent_is_active=lambda: self.server.synthetic_consent,
                user=FakeUser(),
                hass=FakeHass(),
                disclosure_is_approved=lambda entity_id, value: (
                    self.server.synthetic_disclosure and entity_id == 'light.demo_lamp' and value == 'on'
                ),
            )
        except privacy.EntityNotVisible:
            self.respond(404, b'{"error":"not available"}')
            return
        self.respond(200, payload)

    def do_POST(self):
        self.respond(405, b'{"error":"not available"}')

    def do_PUT(self):
        self.respond(405, b'{"error":"not available"}')

    def do_DELETE(self):
        self.respond(405, b'{"error":"not available"}')

    def do_OPTIONS(self):
        self.respond(405, b'{"error":"not available"}')


class LoopbackWireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Owned disposable ephemeral loopback listener. Never bind 0.0.0.0.
        cls.server = HTTPServer(("127.0.0.1", 0), LocalOnlyHandler)
        cls.server.synthetic_consent = True
        cls.server.synthetic_disclosure = True
        cls.port = cls.server.server_address[1]
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def setUp(self):
        self.server.synthetic_consent = True
        self.server.synthetic_disclosure = True

    def request(self, path, method="GET"):
        # http.client uses direct 127.0.0.1 TCP; no HTTP proxy environment.
        conn = HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.request(method, path, headers={"Host": "127.0.0.1"})
            resp = conn.getresponse()
            return resp.status, dict(resp.getheaders()), resp.read()
        finally:
            conn.close()

    def test_binding_is_loopback_and_port_is_ephemeral(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertGreater(self.port, 0)

    def test_authorized_projection_emits_only_two_fields_on_actual_loopback_wire(self):
        status, headers, body = self.request(BASE + "light.demo_lamp")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"entity_id": "light.demo_lamp", "state": "on"})
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertNotIn("Access-Control-Allow-Origin", headers)
        for value in (b"attributes", b"context", b"latitude", b"friendly_name",
                      b"user_id", b"last_updated"):
            self.assertNotIn(value, body)

    def test_denied_and_missing_entities_have_indistinguishable_body_and_code(self):
        denied = self.request(BASE + "person.demo_private")
        missing = self.request(BASE + "sensor.demo_missing")
        self.assertEqual(denied[0], 404)
        self.assertEqual(missing[0], 404)
        self.assertEqual(denied[2], missing[2])
        self.assertNotIn(b"private", denied[2])

    def test_revoked_consent_stops_even_authorized_entity_on_wire(self):
        self.server.synthetic_consent = False
        status, _, body = self.request(BASE + "light.demo_lamp")
        self.assertEqual(status, 404)
        self.assertEqual(body, b'{"error":"not available"}')

    def test_classifier_denial_returns_only_generic_404_on_wire(self):
        self.server.synthetic_disclosure = False
        status, _, body = self.request(BASE + "light.demo_lamp")
        self.assertEqual(status, 404)
        self.assertEqual(body, b'{"error":"not available"}')

    def test_invalid_path_and_encoded_traversal_do_not_expose_state(self):
        for path in ("/_synthetic/other", BASE + "light.demo_lamp/../sensor.secret",
                     BASE + "light.demo_lamp%2F..", BASE + "light.demo_lamp?all=true",
                     "/api/states/light.demo_lamp", BASE + "LIGHT.demo_lamp"):
            with self.subTest(path=path):
                status, _, body = self.request(path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"entity_id", body)

    def test_state_mutating_and_cors_preflight_methods_refused(self):
        for method in ("POST", "PUT", "DELETE", "OPTIONS"):
            with self.subTest(method=method):
                status, _, body = self.request(BASE + "light.demo_lamp", method=method)
                self.assertEqual(status, 405)
                self.assertNotIn(b"light.demo_lamp", body)


if __name__ == "__main__":
    unittest.main()
