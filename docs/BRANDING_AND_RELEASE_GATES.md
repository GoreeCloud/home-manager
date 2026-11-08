# GoreeCloud Home Manager — Branding architecture and release gates

**Status:** Development-stage source import. This document records inspected implementation boundaries, verified decisions, and outstanding acceptance checks. It is not a release approval.

## Verified source baseline (November 7, 2026)

| Responsibility | Current source evidence | Implication |
| --- | --- | --- |
| Home automation backend | Imported home-assistant/core branch master, upstream commit 74cf5a49c63ed8d4d87717844bf14f79c28c9cea | Core public APIs, integrations, and storage contracts should remain intact until migration tests prove otherwise |
| Python package and runtime | pyproject.toml uses package name homeassistant and requires Python >=3.14.2; homeassistant/const.py uses APPLICATION_NAME = HomeAssistant | Do not casually rename internal packages or runtime constants |
| Browser interface | homeassistant/components/frontend/manifest.json pins the external home-assistant-frontend==20261028.4 package | Core source alone cannot produce an independently GC UI-branded frontend; review the precise separately licensed frontend sources and build artifacts first |
| Verified frontend source tag | The home-assistant/frontend tag 20261028.4 resolves to a67b691a451e0b3fc469679b07158f963a61842c; its LICENSE.md is Apache-2.0; the upstream package.json declares the same project name | Tag and license identified, but no complete frontend source audit, build or GC UI integration has been performed |
| Branded CLI source entrypoint | The package metadata defines goreecloud-home-manager as an alias to the unmodified hass entrypoint | Source and built-wheel entrypoint metadata verified; installed invocation and runtime behavior remain untested |
| Current product identity | Root README.rst, UPSTREAM_SOURCE.md, and SECURITY.md identify GoreeCloud Home Manager | Repository-level rebranding is done; runtime UI is still upstream |
| License and provenance | Root LICENSE.md is Apache-2.0; upstream copyright and README preserved | Retain upstream authorship and third-party notices; independent branding does not imply sponsorship |
| Automation | 19 original upstream workflow files are retained out of active workflow paths; inherited templates, funding, and agent guidance are similarly quarantined | Enable only individually reviewed GoreeCloud CI with narrowly scoped permissions |

## Frontend dependency review and integration boundary

The imported Core frontend manifest pins `home-assistant-frontend==20261028.4`. The matching upstream `home-assistant/frontend` tag `20261028.4` resolves to `a67b691a451e0b3fc469679b07158f963a61842c`, and its `LICENSE.md` is Apache-2.0. At this tag, `package.json` declares Node.js `24.22.1`, pnpm `12.15.0`, `postinstall: husky`, `prepack/postpack: pinst`, and a build manager that launches Gulp. The workspace config specifies `minimumReleaseAge`, `trustPolicy: no-downgrade`, a dependency build-script allowlist, and several patched dependencies. These are source-level findings, **not** a completed malware review, dependency audit, or frontend build.

The next compatible implementation boundary is a **separately pinned, independently built frontend**, with upstream licenses and other assets reviewed before any changes to the Core frontend requirement. The GC UI styling, identity, navigation, and UI states must be implemented and screenshot-reviewed on that frontend branch; do not substitute a renamed Python package or an unvalidated CSS injection for a complete runtime rebrand. Protect existing websocket/auth contracts, user configurations, Lovelace dashboards, and device integrations while a separate frontend is tested. Do not execute package install hooks or modified build scripts without source and dependency review.

### Upstream frontend binary artifact evidence

The separately packaged `home-assistant-frontend==20261028.4` release is listed on [PyPI](https://pypi.org/project/home-assistant-frontend/20261028.4/) with a single `py3-none-any` wheel (117,422,576 compressed bytes) and Apache-2.0 license metadata. The official wheel digest is `e5e59b82e63b288323d35886272f2e490ee62f6c7aaa2c56e7ef45e300d44757`. The upstream source at tag `20261028.4` defines a separate `hass_frontend` Python distribution package with a setuptools backend. Only the upstream project's files are being checked. The scoped CI job performs a no-dependency, binary-only wheel download and validates the exact archive without installing, importing, executing, or extracting frontend code.

This is a **supply-chain provenance prerequisite**, not a GoreeCloud-compiled frontend. No assertion is made that this PyPI wheel is reproducible from the pinned Git SHA, that all embedded JavaScript dependencies and branding assets have been audited, or that authentication/UI compatibility is proven. A branded frontend still requires independent source review, a reproducible build, attribution/trademark review, compatibility tests and complete GC UI visual acceptance.

## GoreeCloud UI authority

The design authority is [GoreeCloud UI](https://github.com/GoreeCloud/gc-ui), not the imported upstream frontend. The active design-language standard and semantic tokens govern any future GoreeCloud-controlled screens. Stable Foundations v1.0.1 is scoped to semantic tokens, color, and browser-theme control; it does **not** confer stability on the rest of the experimental component workspace or certify this product.

- Use **GoreeCloud Home Manager** as the full public product name, while keeping existing Home Assistant backend integration identifiers where needed for compatibility.
- Reuse verified GC UI semantic tokens and theme behavior only after resolving the upstream frontend's independent build, licensing, packaging, and configuration interfaces.
- Do not invent mandatory GoreeCloud brand colors. Design choices must retain semantic contrast, keyboard/assistive usability, reduced-motion options, and responsive behavior.
- Inspect rendered login, onboarding, dashboards, automations, devices, integrations, settings, update/error/empty states, and mobile layouts before claiming a complete rebrand.
- Third-party Home Assistant, Open Home Foundation, and device/vendor marks must be reviewed separately; do not imply endorsement.

## Release gates

| Gate | Acceptance evidence | Status |
| --- | --- | --- |
| Import provenance, license and source | Pinned upstream SHA, LICENSE, original README, matching GitHub tree | Verified at initial import |
| Inherited automation containment | Original upstream automation quarantined; read-only checks and hosted CI pass | Verified as of baseline PR #2 |
| Frontend architecture and GC UI compatibility | Exact upstream frontend package assessed, production-branded UI built with GC UI, visual screenshots and user flows validated | Open |
| Pinned upstream frontend wheel provenance | PyPI binary wheel `20261028.4` checked against official SHA-256, distribution license/metadata, ZIP member safety, and bundled asset presence without import/extraction | CI review pending; a verified upstream wheel does not prove GC UI branding or frontend source-build equivalence |
| Dependency and source security | Relevant dependency manifests, updates, permissions, patches, secrets exposure, and scanner findings reviewed | Open |
| Supported Python syntax check | Pinned Python 3.14.10 hosted interpreter compiles selected backend modules and runs source tests | Verified in PR #4 and postmerge CI |
| Package metadata smoke | Manual-only hosted Python 3.14.10 PEP 517 build with hash-verified setuptools 84.0.0; built wheel licensing and dual entrypoints checked without executing Home Assistant | Verified in [workflow run 42416187883](https://github.com/GoreeCloud/home-manager/actions/runs/42416187883); not an installer or runtime test |
| Branded packaging and isolated installation | GoreeCloud development metadata, upstream provenance, wheel installation in an isolated Python 3.14.10 environment and both generated CLI launchers | **Passed** in [PR #6 CI](https://github.com/GoreeCloud/home-manager/actions/runs/42509747839); full dependencies and service runtime still untested |
| Core dependency wheel availability and complete resolution | Python 3.14.10-compatible direct wheels and reviewed transitive graph | **Blocked:** `pymicro-vad==1.0.1` lacks compatible CPython 3.14 wheels on PyPI ([direct-wheel CI](https://github.com/GoreeCloud/home-manager/actions/runs/42512036739)); full pip resolution separately exceeded depth ([issue #9](https://github.com/GoreeCloud/home-manager/issues/9)) |
| Python core build and test | Clean supported Python >=3.14.2 environment, selected core tests and regression checks pass | Open |
| Functional integration and privacy | Secure self-hosted setup, device discovery consent, least privilege, data retention and restore, error handling verified | Open |
| MIPS integration | GoreeShield privacy, Wardveil cybersecurity, GoreeCloud Mesh interoperability, GoreeCloud Identity authentication, and GC UI contracts implemented and tested where applicable | Open |
| Release | Signed/verifiable artifacts as appropriate, rollback, deployment checks, onboarding, supported hardware and release approval | Open |

**Packaged distribution identity:** The rebranded package retains `homeassistant` as the internal Python distribution and preserves Home Assistant Core authorship. The GoreeCloud maintainer, project URLs, upstream source attribution, and **Alpha** development classification distinguish this imported derivative from a released upstream Home Assistant distribution. The first-party review packaging job will install the built wheel into a disposable virtual environment with `--no-index --no-deps --no-compile`, inspect the generated `hass` and `goreecloud-home-manager` launchers and Python metadata, and **will not invoke either command**. This does not validate runtime functionality.

**Package test boundaries:** The manual-only package smoke uses a short-lived hosted runner and fetches the upstream-pinned setuptools 84.0.0 wheel, verifies its PyPI-listed SHA-256, and builds without Home Assistant runtime dependencies or secrets. The wheel inspector checks ZIP member safety, provenance-relevant package metadata, Apache-2.0 license contents, and the dual CLI entrypoints without installing or running Home Assistant. Building may execute the inspected setuptools build backend; it is not a full dependency or malware audit. No wheel is published or deployed.

**Package build evidence (November 7, 2026):** The [manually dispatched hosted workflow](https://github.com/GoreeCloud/home-manager/actions/runs/42416187883) passed all three jobs and built a wheel with SHA-256 `b8d1469d5ceb890de6371b418545731f3ef964df8941718e970346805cd24a4f`; the inspector verified Apache-2.0 metadata, included license, and both console command names. This was neither a runtime service test nor a released distribution.

**Installed package evidence (November 8, 2026):** [PR #6](https://github.com/GoreeCloud/home-manager/pull/6) merged GoreeCloud development-stage package metadata and the first-party/explicitly dispatched install-validation gate. Its [hosted run 42509747839](https://github.com/GoreeCloud/home-manager/actions/runs/42509747839) passed all three jobs; wheel SHA-256 `25e7ab68554376f513eaa9a0d84e78cd84a46632328c22261f633eaf696d6211`. The isolated virtual environment installed the wheel without runtime dependencies and verified two generated launchers; neither launcher or the home automation service was executed. The [post-merge main validation](https://github.com/GoreeCloud/home-manager/actions/runs/42509903897) passed both routine source jobs; its heavier packaging job was intentionally skipped.

**Dependency resolution finding (November 8, 2026):** The upstream-generated `requirements.txt` pins `pymicro-vad==1.0.1`. Its [official PyPI 1.0.1 release](https://pypi.org/project/pymicro-vad/1.0.1/) offers wheels for earlier CPython ABIs but not CPython 3.14. A binary-only direct wheel download on the pinned Python 3.14.10 runner failed in [PR #7 CI](https://github.com/GoreeCloud/home-manager/actions/runs/42512036739), and earlier full `pip` dependency dry runs exceeded resolution depth even with the upstream package constraints. Do **not** remove the package or change its pin without source/API compatibility, security and licensing review. The [full-graph blocker](https://github.com/GoreeCloud/home-manager/issues/9) is separate from a successful dependency-free Home Manager wheel install. **No runnable Core dependency environment has been established.**

**Testing scope:** tools/check_home_manager_import.py is a deterministic *static import invariant check*. It reads bounded local files only, makes no network requests, installs no packages, does not execute imported Home Assistant modules, and cannot establish absence of malicious code, vulnerability freedom, runtime functionality, or released visual quality.

## Next highest-value development steps

1. Inspect the exact home-assistant-frontend==20261028.4 source/package provenance, license, build scripts, API coupling, and upstream asset/trademark constraints; identify the smallest compatible GC UI integration boundary.
2. Review runtime dependency resolution on an isolated Python 3.14.10 runner and run selected Home Assistant Core tests and functional regression smoke before backend edits. The installed-wheel metadata gate is now verified but does not cover runtime dependencies.
3. Implement product-specific branding as a small, reviewable delta with functional/visual regression tests; avoid mass string replacements or breaking integration identifiers.
4. Add controlled release CI only after reviewing the disabled upstream workflows and any needed secrets, publishing targets and permissions.
5. Reconcile the canonical GoreeCloud/GoreeCloud-Github-Repositories.md *in place*, preserving its existing Drive file identity. A Markdown draft or GitHub issue is not a substitute for that update.

No external service, household device, camera, user account, or home network was configured or accessed to complete this documentation.
