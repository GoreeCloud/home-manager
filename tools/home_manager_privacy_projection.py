"""Dependency-free, *unwired* server-side entity projection candidate.

Imported Home Assistant Core checks user.permissions.check_entity(entity_id,
POLICY_READ) before hass.states.get(entity_id). This module emulates that
defensive ordering while enforcing an explicit consent allowlist and returning
only two scalar fields.

This is NOT an HTTP route, authenticated server, trusted permission provider,
GoreeShield integration, deployment, or Home Assistant runtime-tested component.
Use with trusted, already-authenticated Home Assistant-like objects only.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Collection
from typing import Any, Final

POLICY_READ: Final = "read"  # Compare with imported HA constants in tests.
MAX_ALLOWED_IDS: Final = 32
MAX_ENTITY_ID_CHARS: Final = 100
MAX_STATE_CHARS: Final = 120
MAX_RESPONSE_BYTES: Final = 1024
_ENTITY_ID: Final = re.compile(r"[a-z][a-z0-9_]*\.[a-z0-9_]+", re.ASCII)


class EntityNotVisible(Exception):
    """Generic refusal; does not disclose existence or policy."""

    def __init__(self) -> None:
        super().__init__("Entity not available")


def _valid_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= MAX_ENTITY_ID_CHARS
        and _ENTITY_ID.fullmatch(value) is not None
    )


def _validate_allowlist(value: Collection[str]) -> frozenset[str]:
    # Do not accept strings, generators, mutable mapping views, or huge inputs.
    if not isinstance(value, (list, tuple, frozenset)):
        raise EntityNotVisible
    if not 1 <= len(value) <= MAX_ALLOWED_IDS:
        raise EntityNotVisible
    items = frozenset(value) if all(isinstance(x, str) for x in value) else frozenset()
    if len(items) != len(value) or any(not _valid_id(item) for item in items):
        raise EntityNotVisible
    return items


def project_authorized_entity(
    *,
    entity_id: str,
    consented_entity_ids: Collection[str],
    consent_is_active: Callable[[], bool],
    user: Any,
    hass: Any,
    disclosure_is_approved: Callable[[str, str], bool] | None = None,
) -> bytes:
    """Return minimal JSON bytes *before a future HTTP response*.

    Ordering: validate consent scope -> active consent -> per-user POLICY_READ
    -> single state lookup -> trusted scalar disclosure approval -> active
    consent recheck -> minimal serialization.
    No bulk state enumeration, metadata, auth tokens, network, or storage.
    """
    if not _valid_id(entity_id):
        raise EntityNotVisible
    allowed = _validate_allowlist(consented_entity_ids)
    if (entity_id not in allowed or not callable(consent_is_active)
            or not callable(disclosure_is_approved)):
        raise EntityNotVisible

    try:
        if consent_is_active() is not True:
            raise EntityNotVisible
        if user.permissions.check_entity(entity_id, POLICY_READ) is not True:
            raise EntityNotVisible
        state = hass.states.get(entity_id)
        if state is None:
            raise EntityNotVisible
        if state.entity_id != entity_id:
            raise EntityNotVisible
        value = state.state
        if (
            not isinstance(value, str)
            or len(value) > MAX_STATE_CHARS
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
        ):
            raise EntityNotVisible
        # All state strings can be sensitive. Disclose only with an explicit,
        # trusted per-entity/per-value policy approval; no permissive default.
        if disclosure_is_approved(entity_id, value) is not True:
            raise EntityNotVisible
        if consent_is_active() is not True:
            raise EntityNotVisible

        # Never read .as_dict_json, .attributes, timestamps or context.
        payload = json.dumps(
            {"entity_id": entity_id, "state": value},
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(payload) > MAX_RESPONSE_BYTES:
            raise EntityNotVisible
    except Exception:
        # Suppress nested provider exception text; do not reveal existence.
        raise EntityNotVisible from None

    return payload
