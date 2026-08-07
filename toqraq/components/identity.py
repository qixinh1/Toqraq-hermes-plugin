"""Deterministic store key for a complete component identity."""

from __future__ import annotations

import hashlib

from .release import ComponentIdentity

_IDENTITY_FORMAT = b"toqraq-component-identity-v1\0"


def component_identity_key(identity: ComponentIdentity) -> str:
    """Return a collision-resistant storage key for every identity field."""
    digest = hashlib.sha256(_IDENTITY_FORMAT)
    for value in identity.key:
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return digest.hexdigest()
