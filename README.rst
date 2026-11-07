GoreeCloud Home Manager
=======================

**Status: Development-stage rebranded source import. Not a tested release or deployment.**

GoreeCloud Home Manager is a GoreeCloud-branded source import of
`Home Assistant Core <https://github.com/home-assistant/core>`_, the
open-source home automation platform. Its purpose is a self-hosted home
manager within the GoreeCloud ecosystem.

**Upstream:** Home Assistant Core, branch `master`, commit
`74cf5a49c63ed8d4d87717844bf14f79c28c9cea` (imported November 7, 2026).

**Attribution and license:** Copyright remains with the upstream authors
and other respective rights holders. The core source remains distributed
under the Apache License 2.0; see `LICENSE.md <LICENSE.md>`_.
Additional third-party notices and licenses in the source remain applicable.
For the unchanged upstream introduction, see
`UPSTREAM_README.rst <UPSTREAM_README.rst>`_. For a detailed import record,
see `UPSTREAM_SOURCE.md <UPSTREAM_SOURCE.md>`_.

**Rebranding scope:** This initial import establishes the GoreeCloud product
and repository identity. The upstream `homeassistant` Python module,
integration identifiers, packaging, service names, and many user-visible
strings remain unchanged for compatibility. A complete GoreeCloud UI and
runtime rebrand has **not** been implemented or validated. Home Assistant
and its logos are trademarks of their respective rights holders.
This repository is independent and is not affiliated with or endorsed by
the Home Assistant project or the Open Home Foundation.

**Security and automation:** Upstream GitHub Actions workflows and repository
automation configuration have been retained for reference but moved out of
GitHub's active locations. They require a GoreeCloud-specific security,
secrets, publishing, and CI review before reuse. No application code,
dependency installers, workflow jobs, or test suite were executed during
the source import.

**Development and setup:** Review the upstream
`documentation <https://www.home-assistant.io/docs/>`_ and the
`UPSTREAM_README.rst <UPSTREAM_README.rst>`_ for the upstream baseline.
Build, integration, deployment, and GoreeCloud UI acceptance tests remain
outstanding for this imported revision.
