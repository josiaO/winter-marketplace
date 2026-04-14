"""Time-limited signed tokens for admin access to verification uploads (not raw /media/ URLs)."""

from __future__ import annotations

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

SALT = 'seller-verification-media'
MAX_AGE_SEC = 3600

KIND_ID_FRONT = 'id_front'
KIND_ID_BACK = 'id_back'
KIND_SELFIE = 'selfie'
KIND_BUSINESS_CERT = 'business_cert'
KIND_BUSINESS_LICENSE = 'business_license'

_signer = TimestampSigner(salt=SALT)


def sign_verification_media(seller_profile_id: int, kind: str) -> str:
    return _signer.sign(f'{seller_profile_id},{kind}')


def parse_verification_media_token(token: str) -> tuple[int, str]:
    raw = _signer.unsign(token, max_age=MAX_AGE_SEC)
    sid_s, kind = raw.split(',', 1)
    return int(sid_s), kind


__all__ = [
    'MAX_AGE_SEC',
    'KIND_ID_FRONT',
    'KIND_ID_BACK',
    'KIND_SELFIE',
    'KIND_BUSINESS_CERT',
    'KIND_BUSINESS_LICENSE',
    'BadSignature',
    'SignatureExpired',
    'parse_verification_media_token',
    'sign_verification_media',
]
