# Home Manager — server-side minimal entity projection experiment

**Status: isolated first-party source and synthetic tests only; not a Home Assistant component, API endpoint, deployment, production privacy guarantee, or MIPS acceptance.**

This experiments with the privacy gap recorded in [issue #1](https://github.com/GoreeCloud/home-manager/issues/1): the imported Home Assistant WebSocket get_states command returns the entire authorized inventory, and even its targeted GET /api/states/{entity_id} endpoint serializes attributes, context and timestamps for the requested entity *before* client-side filtering.

## Imported source authority

- [homeassistant/components/api/__init__.py](https://github.com/GoreeCloud/home-manager/blob/main/homeassistant/components/api/__init__.py) defines APIEntityStateView.get, which checks user.permissions.check_entity(entity_id, POLICY_READ) before hass.states.get(entity_id).
- [homeassistant/auth/permissions/const.py](https://github.com/GoreeCloud/home-manager/blob/main/homeassistant/auth/permissions/const.py) defines POLICY_READ as read.
- The existing isolated [REST request-plan contract](../ui_preview/src/ha-entity-rest-contract.mjs) has no network transport or real authorization and must not be mistaken for full server-side minimization.

## New pure projection candidate

The [tools/home_manager_privacy_projection.py](../tools/home_manager_privacy_projection.py) function projects a single requested entity to deterministic JSON containing only entity_id and state. It enforces this order:

1. Validate a strictly bounded 1–32 member entity-ID consent allowlist. Refuse any requested ID outside it before invoking permission checks or reading states.
2. Invoke a *trusted, per-request* consent_is_active callback. Reject any result other than literal True.
3. Call the *already-authenticated* principal's permissions.check_entity(requested_id, "read"), requiring literal True. This happens before a single hass.states.get(id) lookup. No bulk state enumeration.
4. Validate the state identifier matches the request, and reject malformed or unbounded scalar state content.
5. Recheck consent immediately before minimal serialization; emit only two schema-fixed fields, bounded at 1024 encoded bytes. Do not inspect or serialize attributes, location, last_changed, context or user metadata. Do not log rejected requests or return underlying exception details.
6. For missing, revoked, unconsented, malformed or unauthorized entities, return the same generic EntityNotVisible exception. Avoid existence or access oracle details.

A separate test suite uses **only fake in-memory Home Assistant-shaped objects**, including dangerous attributes that raise if read, and checks the permission-before-read order against the imported Python source. It tests consent denial, revocation, invalid and duplicate IDs, missing state, permission failure, improper state values and provider exception sanitation. Run python3 -m unittest discover -s tests_goreecloud -p "test_privacy_projection.py" -v in a disposable environment.

## Disposable synthetic HTTP wire regression

The test-only **tests_goreecloud/test_privacy_projection_wire.py** now exercises a tiny, ephemeral **127.0.0.1-only** Python standard-library HTTP server that calls the same pure projection using **fake user, permissions, consent and invented Home Assistant-shaped state**. It is a test fixture, **not** a reusable Home Assistant integration or deployable service. The built-in http.client makes an actual local HTTP request, and the response tests assert that only two JSON fields cross the loopback wire, explicit no-store/nosniff/no-referrer headers appear, no CORS grant is set, denied/missing entities have an indistinguishable response, withdrawn consent blocks reads, malformed paths are refused, and mutating HTTP methods are rejected. Listener lifetime is restricted to test setUpClass/tearDownClass, a random ephemeral port, and 127.0.0.1.

This catches accidental serialization leaks in a mock server environment; it does **not** validate the imported Core runtime, TLS, user authentication, external hostname control, Home Assistant integration registration, replay protection, real secret-bearing values, production logging, service/process isolation, availability, or an approved GoreeShield/Wardveil implementation.

## Real integration and release blockers

This module **has no HTTP/WebSocket route**, bearer token custody, origin/TLS policy, signed authentication, user/consent identity binding, data persistence policy, schema version, rate limiting, control or event API, deployment, logging/monitoring governance, or actual Home Assistant imports. It does not prove race-free consent revocation across threads or processes. Merely projecting a state is not proof that the state value itself is not sensitive: some integrations may encode a secret, person presence or location directly as a scalar. Production must add GoreeShield field/entity classification and consent enforcement, Wardveil threat review, GoreeCloud Identity session policy, Mesh API contracts and GC UI accessibility. The caller must be server-side and already authenticated, and the full private state must never traverse a browser boundary. Review denial side channels, token scope, revocation, cache/HTTP headers, backup/retention, real API permissions, error policies and trust boundaries. Actual inherited Core and optional native dependencies still require separate resolution and integration testing.

**Do not register, expose, or deploy this function as a household API.** Any real Home Assistant integration must pass independent security, privacy and disposable-service end-to-end tests before release.
