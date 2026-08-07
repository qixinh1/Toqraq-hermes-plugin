"""Pure identity and limit validation for one engine-bridge handshake."""

from __future__ import annotations

import hmac
import re
import unicodedata
from dataclasses import dataclass, field

from .bridge_errors import (
    BridgeCredentialMismatchError,
    BridgeHandshakeField,
    BridgeHandshakeMismatchError,
)
from .runtime import RuntimeIdentity, RuntimeRelease, validate_namespaced_id

BRIDGE_CREDENTIAL_BYTES = 32
BRIDGE_CREDENTIAL_HEX_CHARACTERS = BRIDGE_CREDENTIAL_BYTES * 2
BRIDGE_LOOPBACK_HOST = "127.0.0.1"
BRIDGE_ENDPOINT_PATH = "/toqraq/bridge"
MIN_BRIDGE_ENDPOINT_PORT = 1
MAX_BRIDGE_ENDPOINT_PORT = 65_535
MAX_BRIDGE_SESSION_ID_BYTES = 512
MAX_BRIDGE_RUN_REVISION = (1 << 53) - 1
MAX_BRIDGE_CAPABILITIES = 64
MIN_BRIDGE_TEXT_MESSAGE_BYTES = 4_096
MAX_BRIDGE_TEXT_MESSAGE_BYTES = 262_144
MAX_BRIDGE_BINARY_TRANSFER_BYTES = 67_108_864
MAX_BRIDGE_IN_FLIGHT_REQUESTS = 64
COMMON_BRIDGE_TEXT_MESSAGE_BYTES = 262_144
COMMON_BRIDGE_BINARY_TRANSFER_BYTES = 32 * 1024 * 1024
COMMON_BRIDGE_IN_FLIGHT_REQUESTS = 16
MAX_BRIDGE_JSON_DEPTH = 16
MAX_BRIDGE_JSON_NODES = 4_096
MAX_BRIDGE_JSON_COLLECTION_ITEMS = 256
MAX_BRIDGE_REQUEST_ID_CHARACTERS = 128

_CREDENTIAL = re.compile(rf"^[0-9a-f]{{{BRIDGE_CREDENTIAL_HEX_CHARACTERS}}}$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


@dataclass(frozen=True, slots=True, kw_only=True)
class BridgeListenerEndpoint:
    """Non-secret address of one process-local engine bridge listener."""

    port: int

    def __post_init__(self) -> None:
        """Require one concrete operating-system-assigned TCP port."""
        _require_integer_range(
            self.port,
            minimum=MIN_BRIDGE_ENDPOINT_PORT,
            maximum=MAX_BRIDGE_ENDPOINT_PORT,
            label="bridge listener port",
        )

    @property
    def host(self) -> str:
        """Return the only network interface accepted by the bridge contract."""
        return BRIDGE_LOOPBACK_HOST

    @property
    def path(self) -> str:
        """Return the exact WebSocket upgrade path."""
        return BRIDGE_ENDPOINT_PATH

    @property
    def url(self) -> str:
        """Return the complete URL accepted by an engine-native client."""
        return f"ws://{self.host}:{self.port}{self.path}"


def validate_bridge_session_id(value: str) -> str:
    """Return one bounded Unicode Hermes session identity or raise."""
    if not isinstance(value, str) or not value:
        raise ValueError("bridge session ID is invalid")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("bridge session ID is invalid") from exc
    if len(encoded) > MAX_BRIDGE_SESSION_ID_BYTES or any(
        unicodedata.category(character).startswith("C") for character in value
    ):
        raise ValueError("bridge session ID is invalid")
    return value


def validate_bridge_credential(value: str) -> str:
    """Return one canonical 256-bit credential encoding or raise."""
    if not isinstance(value, str) or _CREDENTIAL.fullmatch(value) is None:
        raise ValueError("bridge credential is invalid")
    return value


def validate_bridge_run_revision(value: int) -> int:
    """Return one positive cross-language-safe run revision or raise."""
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= MAX_BRIDGE_RUN_REVISION
    ):
        raise ValueError("bridge run revision is invalid")
    return value


def validate_bridge_request_id(value: str) -> str:
    """Return one bounded connection-owned JSON-RPC request ID or raise."""
    if (
        not isinstance(value, str)
        or len(value) > MAX_BRIDGE_REQUEST_ID_CHARACTERS
        or _REQUEST_ID.fullmatch(value) is None
    ):
        raise ValueError("bridge request ID is invalid")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class BridgeOwnerKey:
    """Authenticated run identity inside one Hermes session."""

    session_id: str
    run_revision: int

    def __post_init__(self) -> None:
        """Reject identities that cannot be compared across bridge languages."""
        validate_bridge_session_id(self.session_id)
        validate_bridge_run_revision(self.run_revision)


@dataclass(frozen=True, slots=True, kw_only=True)
class BridgeRequestReference:
    """Reference to one request owned by the authenticated connection."""

    value: str

    def __post_init__(self) -> None:
        """Use the same exact identity syntax as request and response envelopes."""
        validate_bridge_request_id(self.value)


@dataclass(frozen=True, slots=True, kw_only=True)
class BridgeLimits:
    """Pre-feature limits negotiated during the handshake."""

    max_text_message_bytes: int
    max_binary_transfer_bytes: int
    max_in_flight_requests: int

    def __post_init__(self) -> None:
        """Reject booleans and values outside the stable protocol bounds."""
        _require_integer_range(
            self.max_text_message_bytes,
            minimum=MIN_BRIDGE_TEXT_MESSAGE_BYTES,
            maximum=MAX_BRIDGE_TEXT_MESSAGE_BYTES,
            label="bridge text-message limit",
        )
        _require_integer_range(
            self.max_binary_transfer_bytes,
            minimum=1,
            maximum=MAX_BRIDGE_BINARY_TRANSFER_BYTES,
            label="bridge binary-transfer limit",
        )
        _require_integer_range(
            self.max_in_flight_requests,
            minimum=1,
            maximum=MAX_BRIDGE_IN_FLIGHT_REQUESTS,
            label="bridge in-flight request limit",
        )

    def constrained_by(self, other: BridgeLimits) -> BridgeLimits:
        """Return the stricter value for every independently owned limit."""
        if not isinstance(other, BridgeLimits):
            raise ValueError("bridge peer limits are invalid")
        return BridgeLimits(
            max_text_message_bytes=min(
                self.max_text_message_bytes,
                other.max_text_message_bytes,
            ),
            max_binary_transfer_bytes=min(
                self.max_binary_transfer_bytes,
                other.max_binary_transfer_bytes,
            ),
            max_in_flight_requests=min(
                self.max_in_flight_requests,
                other.max_in_flight_requests,
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BridgeHandshakeOffer:
    """Validated identity offered by one untrusted engine process."""

    credential: str = field(repr=False)
    owner: BridgeOwnerKey
    runtime_identity: RuntimeIdentity
    bridge_id: str
    protocol: str
    capability_ids: frozenset[str]
    limits: BridgeLimits

    def __post_init__(self) -> None:
        """Reject malformed values before any expected identity is compared."""
        validate_bridge_credential(self.credential)
        if not isinstance(self.owner, BridgeOwnerKey):
            raise ValueError("bridge offer owner is invalid")
        if not isinstance(self.runtime_identity, RuntimeIdentity):
            raise ValueError("bridge offer runtime identity is invalid")
        validate_namespaced_id(self.bridge_id)
        _validate_protocol(self.protocol)
        _validate_capabilities(self.capability_ids)
        if not isinstance(self.limits, BridgeLimits):
            raise ValueError("bridge offer limits are invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class BridgeHandshakeExpectation:
    """Immutable launch facts accepted by one bridge listener."""

    credential: str = field(repr=False)
    owner: BridgeOwnerKey
    release: RuntimeRelease
    limits: BridgeLimits

    def __post_init__(self) -> None:
        """Validate exact launch facts without inventing native capabilities."""
        validate_bridge_credential(self.credential)
        if not isinstance(self.owner, BridgeOwnerKey):
            raise ValueError("bridge expectation owner is invalid")
        if not isinstance(self.release, RuntimeRelease):
            raise ValueError("bridge expectation release is invalid")
        if not isinstance(self.limits, BridgeLimits):
            raise ValueError("bridge expectation limits are invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class BridgeHandshakeAcceptance:
    """Identity and effective limits returned after exact authentication."""

    owner: BridgeOwnerKey
    protocol: str
    capability_ids: frozenset[str]
    limits: BridgeLimits

    def __post_init__(self) -> None:
        """Keep the accepted result valid if constructed outside the validator."""
        if not isinstance(self.owner, BridgeOwnerKey):
            raise ValueError("bridge acceptance owner is invalid")
        _validate_protocol(self.protocol)
        _validate_capabilities(self.capability_ids)
        if not isinstance(self.limits, BridgeLimits):
            raise ValueError("bridge acceptance limits are invalid")


def validate_bridge_handshake(
    offer: BridgeHandshakeOffer,
    expected: BridgeHandshakeExpectation,
) -> BridgeHandshakeAcceptance:
    """Authenticate every exact owner, runtime, bridge, and capability fact."""
    if not isinstance(offer, BridgeHandshakeOffer) or not isinstance(
        expected, BridgeHandshakeExpectation
    ):
        raise ValueError("bridge handshake values are invalid")
    if not hmac.compare_digest(offer.credential, expected.credential):
        raise BridgeCredentialMismatchError()
    if offer.owner.session_id != expected.owner.session_id:
        _mismatch(BridgeHandshakeField.SESSION_ID)
    if offer.owner.run_revision != expected.owner.run_revision:
        _mismatch(BridgeHandshakeField.RUN_REVISION)

    actual = offer.runtime_identity
    required = expected.release.identity
    if actual.engine_id != required.engine_id:
        _mismatch(BridgeHandshakeField.ENGINE_ID)
    if actual.version != required.version:
        _mismatch(BridgeHandshakeField.ENGINE_VERSION)
    if actual.build_id != required.build_id:
        _mismatch(BridgeHandshakeField.BUILD_ID)
    if actual.distribution_id != required.distribution_id:
        _mismatch(BridgeHandshakeField.DISTRIBUTION_ID)
    if actual.platform != required.platform:
        _mismatch(BridgeHandshakeField.PLATFORM)
    if actual.architecture != required.architecture:
        _mismatch(BridgeHandshakeField.ARCHITECTURE)
    if offer.bridge_id != expected.release.bridge_id:
        _mismatch(BridgeHandshakeField.BRIDGE_ID)
    if offer.protocol != expected.release.bridge_protocol:
        _mismatch(BridgeHandshakeField.PROTOCOL)
    if offer.capability_ids != expected.release.bridge_capability_ids:
        _mismatch(BridgeHandshakeField.CAPABILITIES)

    return BridgeHandshakeAcceptance(
        owner=expected.owner,
        protocol=expected.release.bridge_protocol,
        capability_ids=expected.release.bridge_capability_ids,
        limits=expected.limits.constrained_by(offer.limits),
    )


def _validate_protocol(value: str) -> str:
    """Require the same bounded opaque form used by runtime releases."""
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", value) is None
    ):
        raise ValueError("bridge protocol is invalid")
    return value


def _validate_capabilities(value: frozenset[str]) -> None:
    """Require one bounded immutable native capability set."""
    if not isinstance(value, frozenset) or len(value) > MAX_BRIDGE_CAPABILITIES:
        raise ValueError("bridge capability collection is invalid")
    for capability_id in value:
        validate_namespaced_id(capability_id)


def _require_integer_range(value: int, *, minimum: int, maximum: int, label: str) -> int:
    """Reject boolean and non-integer values before applying a closed range."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} is invalid")
    return value


def _mismatch(field: BridgeHandshakeField) -> None:
    """Raise one stable mismatch without retaining compared values."""
    raise BridgeHandshakeMismatchError(field=field)


COMMON_BRIDGE_LIMITS = BridgeLimits(
    max_text_message_bytes=COMMON_BRIDGE_TEXT_MESSAGE_BYTES,
    max_binary_transfer_bytes=COMMON_BRIDGE_BINARY_TRANSFER_BYTES,
    max_in_flight_requests=COMMON_BRIDGE_IN_FLIGHT_REQUESTS,
)
