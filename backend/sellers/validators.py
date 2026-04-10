import os

from django.core.exceptions import ValidationError

MAX_UPLOAD_BYTES = 5 * 1024 * 1024

IMAGE_EXT = {'.jpg', '.jpeg', '.png'}
DOC_EXT = IMAGE_EXT | {'.pdf'}


def _file_size(f):
    size = getattr(f, 'size', None)
    if size is not None:
        return size
    pos = f.tell()
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(pos)
    return size


def validate_file_size(f):
    if _file_size(f) > MAX_UPLOAD_BYTES:
        raise ValidationError('File must be 5MB or smaller.')


def _ext(name):
    return os.path.splitext((name or '').lower())[1]


def validate_id_front_upload(f):
    validate_file_size(f)
    ext = _ext(getattr(f, 'name', ''))
    if ext not in DOC_EXT:
        raise ValidationError('Allowed types: JPG, PNG, or PDF.')


def validate_selfie_upload(f):
    validate_file_size(f)
    ext = _ext(getattr(f, 'name', ''))
    if ext not in IMAGE_EXT:
        raise ValidationError('Selfie must be a JPG or PNG image.')


def validate_business_certificate_upload(f):
    validate_file_size(f)
    ext = _ext(getattr(f, 'name', ''))
    if ext not in DOC_EXT:
        raise ValidationError('Allowed types: JPG, PNG, or PDF.')
