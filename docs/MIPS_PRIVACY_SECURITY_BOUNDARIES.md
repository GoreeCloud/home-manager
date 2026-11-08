# GoreeCloud Home Manager — MIPS, Privacy and Security Boundaries

**Status:** Security/privacy requirements mapped to the imported source. **Integration design and acceptance are open; no deployed system is implied.**

**Scope:** Home Assistant Core `master` import `74cf5a49c63ed8d4d87717844bf14f79c28c9cea`, preserved Python distribution `homeassistant`, and the separately pinned frontend `20261028.4`. Applies to the source at [GoreeCloud/home-manager](https://github.com/GoreeCloud/home-manager). This document contains no deployment topology, private household identifiers, tokens, accounts, or device data.

## Verified source surfaces

| Imported Core source | Verified exposed boundary | Current acceptance |
| --- | --- | --- |
| `homeassistant/components/http/__init__.py` | HTTP configuration schema includes optional SSL certificate/key, CORS origins, trusted proxy/X-Forwarded-For settings, IP ban and login-attempt settings, and X-Frame-Options | Source identified; defaults, deployment settings and negative-path runtime tests **not validated** for GoreeCloud |
| `homeassistant/components/auth/__init__.py` | OAuth-style authorization-code and refresh-token handling, revocation and long-lived-token capabilities are documented in the source | Existing Home Assistant authentication must remain authoritative until an independently tested adapter is approved |
| `homeassistant/components/websocket_api/__init__.py` | WebSocket commands and authorization decorators (`ws_require_user`, `require_admin`) are registered | Review per-command permissions and authentication during functional tests; no general authorization guarantee |
| `homeassistant/components/onboarding/__init__.py` | Onboarding has user, configuration, integration and analytics steps and a private onboarding store | Verify consent and first-run states from an actual frontend before acceptance |
| `homeassistant/components/analytics/__init__.py` | An analytics integration exists with preference handling and a configured snapshots URL | Treat outbound telemetry and stored preferences as privacy review areas; do **not** infer opt-in/out defaults from these files alone |
| `homeassistant/components/frontend/manifest.json` | Frontend integration pins `home-assistant-frontend==20261028.4` | GoreeCloud UI rebrand, bundled asset review, and visual tests are **open** |

These are selected source inspections, **not** a comprehensive repository security assessment or runtime penetration test.

## Five MIPS — ownership, applicability and gate

| System | Applicability to Home Manager | Required consumer behavior | Current evidence |
| --- | --- | --- | --- |
| **GoreeCloud UI** | Applicable to browser/mobile interaction | Use the authoritative GC UI token/theme and component contract for login, onboarding, navigation, dashboard, settings and error states; preserve compatibility with upstream frontend APIs | [GC UI](https://github.com/GoreeCloud/gc-ui) has a scoped Stable Foundations release; this consumer has **not** migrated |
| **GoreeShield** (privacy) | Applicable to analytics, consent, connected-device metadata, audit/retention and sharing | Data minimization, purpose-scoped consent, opt-out/withdrawal, export/deletion semantics, no unauthorized third-party transfer; fail privacy-safe when central policy service is unavailable | [GoreeShield](https://github.com/GoreeCloud/goreeshield) lists experimental work and does not advertise a verified production policy API. **Not integrated** |
| **Wardveil** (cybersecurity) | Applicable to vulnerability management, protected HTTP/API boundaries and security events | Local secure defaults, least privilege, bounded incident signals and authenticated alert routing; avoid logging secrets or raw household content; require authorization before any remediation | [Wardveil](https://github.com/GoreeCloud/wardveil) states a development-only prototype with no deployed security response. **Not integrated** |
| **GoreeCloud Identity** | Applicable where shared sign-in or federation is authorized | Retain existing Home Assistant auth unless a tested, scoped OIDC/SAML adapter supplies explicit account mapping, token validation, logout/revocation and recovery; never let frontend styling bypass auth | [Identity](https://github.com/GoreeCloud/identity) currently documents development-only Keycloak and an adapter with unresolved licensing. **Not suitable for production reuse without review** |
| **GoreeCloud Mesh** | Applicable to approved cross-product events/API and workflow coordination | Use an audited adapter with least-privilege service identity, explicit purpose/consent, schemas, replay/idempotency controls, timeouts, offline behavior and failure isolation; no ambient trust | [Mesh](https://github.com/GoreeCloud/mesh) has a synthetic local reference, not a verified Home Manager connector. **Not integrated** |

The relevant [MIPS repositories](https://github.com/GoreeCloud) express scope and maturity; a repository link or planned adapter is **not proof of working integration**. No final cross-product API, client secret, token exchange, or service endpoint is selected in this document.

## Threats and verification gates

| Priority | Risk scenario | Required control and evidence before release |
| --- | --- | --- |
| P1 | Unauthorized access to household controls or data | Test login, refresh/revoke, WebSocket/HTTP unauthorized and lower-privilege cases against a disposable supported runtime; no default admin bypass |
| P1 | Accidental public network exposure | Audit bind address, TLS, reverse-proxy trust, allowed origins, authentication, and firewall/routing decisions; test from an isolated network namespace before exposing services |
| P1 | Telemetry or device metadata leaving the system without informed consent | Audit analytics/preferences, outbound hosts and integrations; test first run, consent denied, consent revoked, and disconnected operation; log no private payloads |
| P1 | Unreviewed dependencies or frontend assets | Review pinned Core and frontend dependency/lockfiles, install hooks, third-party license notices, artifact provenance, vulnerability advisories, and update/rollback plan |
| P1 | Credential disclosure or privilege escalation through integration bridges | No secrets in public GitHub/CI/logs; forbid transparent delegation of Home Assistant admin credentials to MIPS services; map scopes and protect rotations |
| P2 | Destructive automations or repeated actions | Require explicit privileged authorization, idempotency/replay limits, bounds, rate limits, and reversible failure states for Mesh/automation consumers |
| P2 | Loss of user settings during updates | Test backup/restore, configuration migrations, compatible frontend versions, rollbacks and independent restore in disposable test data |
| P2 | Visual security ambiguity and inaccessible recovery | GC UI screenshot-led checks for login, permission denied, loading/error/offline states and alternative input/assistive operation on supported screens |

## Integration sequencing

1. Complete isolated Core dependency resolution and supported-Python installation/runtime tests without accessing real household devices.
2. Audit the pinned frontend source and build controls, then implement a compatible GC UI-branded frontend in an independent reviewable branch. Validate sign-in and permission boundaries with representative screenshots and functional tests.
3. Record exact MIPS producer/consumer contracts and their licensing, version, availability and authority. Until accepted, keep each optional adapter **disabled and fail-closed**; preserve local standalone functionality.
4. Test genuine positive/negative authorization and privacy flows in synthetic data, including offline/unavailable MIPS services, token revocation, retry/idempotency and restoration.
5. Only after security/privacy, frontend, deployment and rollback evidence passes should anyone propose an Anchor/Stable release or installation on an authorized home network.

## Evidence boundary

The earlier wheel-build and isolated `--no-deps` install CI verified Python packaging and two console launchers. It did not import the Home Assistant runtime, start services, validate frontend screens, scan all dependencies, connect to devices, or establish a working MIPS integration. See [release-gate ledger](BRANDING_AND_RELEASE_GATES.md) and [release issue #1](https://github.com/GoreeCloud/home-manager/issues/1).

This record is a **public source-level release checklist**, not a substitute for the original private GoreeCloud governance, implementation, integration tests, or consent decisions.