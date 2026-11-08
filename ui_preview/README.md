# GoreeCloud Home Manager — GC UI interface concept

**Scope: development-only synthetic browser preview. Not the Home Assistant frontend, not a production service, and not a device controller.**

This separate first-party HTML/CSS/JavaScript interface explores Home Manager navigation, synthetic room/device inventory, concept automations, privacy disclosure, accessible focus behavior, mobile floating dock, and session-only light/dark/custom-color controls. It uses official [GoreeCloud UI Foundations 1.0.1](https://github.com/GoreeCloud/gc-ui/releases/tag/foundations-v1.0.1) semantic tokens, color engine, and theme controller. Experimental GC UI alpha components are **not** used.

## Verified third-party/component boundary

- Exact GitHub release archive: **goreecloud-gc-ui-1.0.1.tgz**; SHA-256 **275d7e6dc9503b2e74b3190bcecf176d73d2345860e8a20fa5faa3b326cd2298**; source commit **7e0b61ee70af2edb87aa736cca483425f0aacaf4**; Apache-2.0.
- The existing **tools/check_gc_ui_foundations_asset.py** validates the unmodified archive. **tools/stage_gc_ui_home_manager_preview.py** verifies its provenance manifest and copies only **four allowlisted original assets**: source index, color engine, theme runtime, and semantic token stylesheet. No npm install or source build.
- The generated **vendor/** directory is local and gitignored. Source archive and assets are never republished or conflated with GoreeCloud-owned implementation code.
- The optional example accent seed is a concept preference, **not** a GoreeCloud official brand color. Actual GC UI visual acceptance remains a separate review.

## Local preview with a verified official archive

Use a private disposable development environment, not a household server or device. Review the source before use. With the original 1.0.1 archive downloaded from the official GitHub release:

1. Validate it with **python3 tools/check_gc_ui_foundations_asset.py --archive /path/to/goreecloud-gc-ui-1.0.1.tgz --report /tmp/gc-ui-asset-report.json**.
2. Create the parent **ui_preview/vendor/** directory. Run **python3 tools/stage_gc_ui_home_manager_preview.py --archive /path/to/goreecloud-gc-ui-1.0.1.tgz --output-dir ui_preview/vendor/gc-ui**.
3. From the repository root, run **python3 -m http.server 4173 --bind 127.0.0.1**, then browse **http://127.0.0.1:4173/ui_preview/**.
4. Run **node --test ui_preview/tests/preview.test.mjs** to check fixture and source contracts. This is not a screenshot or Home Assistant integration acceptance test.

The hosted review CI uses only the official GitHub asset, pinned checksum and built-in Node test runner. **No data leaves the browser preview:** CSP disables external connections and scripts, no fetch/WebSocket calls exist, devices and spaces are fictional, and theme preferences use session-only, nonpersistent storage. The preview does not request Bluetooth, camera, microphone, location or home automation permissions. There are no action buttons pretending to control real devices.

## Home Assistant read-only protocol contract — tests only

The source-only module **src/hass-readonly-contract.mjs** is not imported by the actual preview UI and does not create any browser WebSocket. Its explicitly simulated message flow matches the imported Python code:

- **homeassistant/components/websocket_api/const.py**: endpoint path **/api/websocket**.
- **homeassistant/components/websocket_api/auth.py**: server **auth_required**, client **auth** with short-lived in-memory **access_token**, server **auth_ok**/**auth_invalid**.
- **homeassistant/components/websocket_api/commands.py**: authenticated client **get_states** with an integer request ID and matching **result** response.

The fail-closed contract accepts at most 32 explicitly allowlisted entity IDs, recognizes only the authentication and read-only state request, rejects out-of-order, malformed or oversized responses, drops credentials after sending, and projects selected states to **entity_id** and **state** only (discarding attributes, coordinates, contexts and timestamps). Its synthetic tests explicitly refuse permission errors, unexpected event messages, malformed state values, duplicate IDs and stale responses. Test with **node --test ui_preview/tests/hass-readonly-contract.test.mjs**.

**Important privacy limitation:** the upstream **get_states** command sends *all entities permitted by Home Assistant authorization* before our local projection. Client-side filtering **does not** meet a strict GoreeShield data-minimization boundary, prevent authorized sensitive device states from reaching the browser, or grant a safe production path. A future consent-reviewed, server-side resource filter and/or dedicated constrained API is needed; do not run this module against a household instance or enter credentials. HA frontend auth/session, rate limits, origin/TLS checks, incremental subscriptions, error handling, UI permissions and real integration remain entirely untested and out of scope.

## Alternative targeted entity GET contract (no requests sent)

The independently source-grounded **src/ha-entity-rest-contract.mjs** prepares a request *description* for the imported Home Assistant Core **GET /api/states/{entity_id}** endpoint. Unlike the broad WebSocket **get_states**, the imported **homeassistant/components/api/__init__.py** implements this route in **APIEntityStateView**, enforces **user.permissions.check_entity(entity_id, POLICY_READ)** server-side and returns HTTP 404 for nonexistent authorized entities. Bearer-token authentication is implemented in imported **homeassistant/components/http/auth.py**.

This is a **pure no-network** contract: permitted IDs must be explicitly listed, a single URL path is assembled from a strictly validated ID, the only permitted method is GET, redirects are refused in the request plan, response status and bounded JSON are checked, and the caller receives only an exact matching **entity_id/state** pair. A 401, 403, 404, redirect or unexpected result fails closed. No Home Assistant socket, host, origin, authorization token, household instance or device is connected. The contract uses an in-memory fake response in tests only. Run **node --test ui_preview/tests/ha-entity-rest-contract.test.mjs**.

**Residual privacy/security gap:** Even this selective upstream endpoint returns the requested entity's full attributes/context before the local projection drops them. Future production use needs a reviewed confidential token custodian, direct same-origin/TLS or trusted proxy enforcement, separate user consent, server-side field minimization, correct Home Assistant per-entity authorization, failure/revocation handling, and operational rate/concurrency limits. Do not interpret a pure request plan as consent, a secure HTTP client, a working frontend integration or a production release.

## Product integration and release work still required

This page is **not** wired to the Home Assistant frontend serving code or its hass_frontend package. The upstream separate frontend remains pinned at version 20261028.4; the Home Assistant backend, manifests, auth, WebSockets, onboarding, integrations and settings have not been substituted, renamed or deployed. A compatible branded frontend must be built from reviewed upstream source, retaining license/trademark attribution and actual API contracts. Follow screenshot-led review across desktop/mobile, light/dark/forced-color, RTL, keyboard, screen readers, and focus/errors/empty states before declaring visual acceptance.

GoreeShield privacy consent, Wardveil cybersecurity and least privileges, GoreeCloud Mesh integration, GoreeCloud Identity and GC UI remain separate MIPS/release gates. Full Python dependency resolution and the PyRIC Bluetooth recovery privilege/license blocker remain open in [issue #9](https://github.com/GoreeCloud/home-manager/issues/9). General release tracking remains in [issue #1](https://github.com/GoreeCloud/home-manager/issues/1) and [the release ledger](../docs/BRANDING_AND_RELEASE_GATES.md).
