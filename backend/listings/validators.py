"""
Validators for listing media uploads.
"""
import os
from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.avi', '.mkv'}
ALLOWED_MEDIA_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS

# Allowed MIME types
ALLOWED_IMAGE_MIMETYPES = {
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/gif',
    'image/webp'
}
ALLOWED_VIDEO_MIMETYPES = {
    'video/mp4',
    'video/webm',
    'video/quicktime',  # .mov
    'video/x-msvideo',  # .avi
    'video/x-matroska'  # .mkv
}
ALLOWED_MEDIA_MIMETYPES = ALLOWED_IMAGE_MIMETYPES | ALLOWED_VIDEO_MIMETYPES

# Size limits in bytes
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB


def validate_media_file(file, max_size=None):
    """
    Validate a media file for type and size.
    
    Args:
        file: Django UploadedFile object
        max_size: Maximum file size in bytes (optional, uses default if not provided)
    
    Returns:
        tuple: (is_video: bool, media_type: str)
    
    Raises:
        ValidationError: If file is invalid
    """
    # Check file extension
    file_name = file.name.lower()
    file_ext = os.path.splitext(file_name)[1]
    
    if file_ext not in ALLOWED_MEDIA_EXTENSIONS:
        raise ValidationError(
            f"File type '{file_ext}' is not allowed. "
            f"Allowed types: {', '.join(sorted(ALLOWED_MEDIA_EXTENSIONS))}"
        )
    
    # Determine if it's a video or image
    is_video = file_ext in ALLOWED_VIDEO_EXTENSIONS
    media_type = 'video' if is_video else 'image'
    
    # Check file size
    if max_size is None:
        max_size = MAX_VIDEO_SIZE if is_video else MAX_IMAGE_SIZE
    
    if file.size > max_size:
        size_mb = max_size / (1024 * 1024)
        file_size_mb = file.size / (1024 * 1024)
        raise ValidationError(
            f"File '{file.name}' is too large ({file_size_mb:.2f}MB). "
            f"Maximum size for {media_type}s is {size_mb}MB."
        )
    
    # Check MIME type if available
    if hasattr(file, 'content_type') and file.content_type:
        if file.content_type not in ALLOWED_MEDIA_MIMETYPES:
            # Warn but don't fail if extension is valid (browsers sometimes send wrong MIME)
            pass
    
    return is_video, media_type


@deconstructible
class MediaFileValidator:
    """
    Django validator for media files.
    Can be used in model fields.
    """
    def __init__(self, max_size=None):
        self.max_size = max_size
    
    def __call__(self, file):
        validate_media_file(file, max_size=self.max_size)
    
    def __eq__(self, other):
        return (
            isinstance(other, MediaFileValidator) and
            self.max_size == other.max_size
        )
