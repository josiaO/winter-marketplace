"""Validate commerce file uploads (shipment media, dispute evidence)."""
from __future__ import annotations

from django.conf import settings

from escrow_engine.upload_validation import dispute_upload_limits


def commerce_upload_limits():
    esc_max, esc_types = dispute_upload_limits()
    max_bytes = int(getattr(settings, 'COMMERCE_UPLOAD_MAX_BYTES', esc_max))
    types = getattr(settings, 'COMMERCE_UPLOAD_ALLOWED_CONTENT_TYPES', None)
    allowed = frozenset(types) if types is not None else esc_types
    return max_bytes, allowed


def validate_commerce_upload_file(uploaded_file) -> None:
    """Raises ValueError if file is too large or disallowed content type."""
    if uploaded_file is None:
        return
    max_bytes, allowed = commerce_upload_limits()
    size = getattr(uploaded_file, 'size', None)
    if size is not None and size > max_bytes:
        raise ValueError(f'File exceeds maximum size of {max_bytes} bytes.')

    raw_ct = getattr(uploaded_file, 'content_type', None) or ''
    content_type = raw_ct.split(';')[0].strip().lower()
    if content_type and content_type not in allowed:
        raise ValueError(f'File type "{content_type}" is not allowed.')


def validate_commerce_upload_files(*, video=None, images=None) -> None:
    validate_commerce_upload_file(video)
    for f in images or []:
        validate_commerce_upload_file(f)
