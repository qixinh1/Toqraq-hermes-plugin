"""Renderer-owned native preview attachment contracts."""

from __future__ import annotations

from .base import ContractModel
from .geometry import RectValue
from .identifiers import AttachmentId, HermesSessionId


class NativePreviewAttachRequest(ContractModel):
    """Attach one ready native surface to one Desktop pane owner."""

    session_id: HermesSessionId
    attachment_id: AttachmentId
    pane_rect: RectValue


class NativePreviewPaneRequest(ContractModel):
    """Follow the latest physical pane geometry for one attachment."""

    session_id: HermesSessionId
    attachment_id: AttachmentId
    pane_rect: RectValue


class NativePreviewVisibleRequest(ContractModel):
    """Change preview visibility without changing ownership."""

    session_id: HermesSessionId
    attachment_id: AttachmentId
    visible: bool


class NativePreviewDetachRequest(ContractModel):
    """Restore one exact Desktop-owned native preview mutation."""

    session_id: HermesSessionId
    attachment_id: AttachmentId


class PreviewOperationResult(ContractModel):
    """Acknowledgement for one completed idempotent preview operation."""

    ok: bool
