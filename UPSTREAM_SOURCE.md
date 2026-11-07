# GoreeCloud Home Manager — Source Import and Attribution

- **Product name:** GoreeCloud Home Manager
- **GoreeCloud repository:** https://github.com/GoreeCloud/home-manager
- **Upstream repository:** https://github.com/home-assistant/core
- **Imported upstream branch:** `master` (released-code branch, not upstream default `dev`)
- **Imported upstream commit:** `74cf5a49c63ed8d4d87717844bf14f79c28c9cea`
- **Import date:** 2026-11-07
- **Import method:** Exact tracked-file source snapshot copied into a new Git repository with a fresh root commit. The upstream branch and commit SHA are documented above; historical upstream ancestry is not included.
- **Primary upstream license:** Apache-2.0 — see `LICENSE.md`.
- **Original upstream project introduction:** `UPSTREAM_README.rst`.
- **Independence:** Not an official Home Assistant release and no endorsement by the Home Assistant project or Open Home Foundation.

## Deliberate import-specific changes

1. Created this provenance record and a GoreeCloud-facing root `README.rst`; original README retained as `UPSTREAM_README.rst`.
2. Retained upstream Python package names, integration identifiers, and API behavior. This is a branded import baseline, **not** a fully rebranded runtime.
3. Moved `.github/workflows/` to `.github/upstream-workflows-disabled/`. Imported workflows must not automatically execute against GoreeCloud credentials or publish upstream packages.
4. Moved upstream `CODEOWNERS` and `.github/dependabot.yml`, where present, into `.github/upstream-config-disabled/` pending an ownership and dependency-update policy review.
5. Did not install dependencies, run source code, start services, or deploy. A clean-room build/test and security review are required before releases.

## Ongoing obligations

- Keep upstream license and required third-party credits intact; do not present upstream authorship as GoreeCloud-authored.
- Independently assess third-party brands, images, package names, service identifiers, and trademark use before changing or distributing branding.
- Pin and verify source revisions when updating; review diff, dependencies, workflows, privacy, runtime permissions, and migration effects.
- Implement GoreeCloud UI only against verified design-system tokens and components; respect GoreeShield privacy, Wardveil security, GoreeCloud Mesh integration and GoreeCloud Identity requirements.
- Replace or safely regenerate CI workflows deliberately before enabling any GitHub Actions execution.
