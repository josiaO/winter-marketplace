"""
Validate dispute / evidence uploads (size and MIME allowlist).
"""
from __future__ import annotations

from django.conf import settings

_DEFAULT_MAX_BYTES = 15 * 1024 * 1024
_DEFAULT_TYPES = frozenset({
    'image/jpeg',
    'image/png',
    'image/gif',
    'image/webp',
    'video/mp4',
    'video/webm',
})


def dispute_upload_limits():
    max_bytes = int(
        getattr(settings, 'ESCROW_DISPUTE_UPLOAD_MAX_BYTES', _DEFAULT_MAX_BYTES)
    )
    types = getattr(settings, 'ESCROW_DISPUTE_UPLOAD_CONTENT_TYPES', None)
    allowed = frozenset(types) if types else _DEFAULT_TYPES
    return max_bytes, allowed


def validate_dispute_upload_file(uploaded_file) -> None:
    """
    Raises ValueError if the uploaded file is too large or not an allowed type.
    """
    if uploaded_file is None:
        return
    max_bytes, allowed = dispute_upload_limits()
    size = getattr(uploaded_file, 'size', None)
    if size is not None and size > max_bytes:
        raise ValueError(f'File exceeds maximum size of {max_bytes} bytes.')

    raw_ct = getattr(uploaded_file, 'content_type', None) or ''
    content_type = raw_ct.split(';')[0].strip().lower()
    if content_type and content_type not in allowed:
        raise ValueError(f'File type "{content_type}" is not allowed.')
