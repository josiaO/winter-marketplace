import os
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from core.models.base import BaseModel

def upload_to_marketplace(instance, filename):
    """Dynamic upload path: marketplace/<vertical>/<listing_id>/<filename>"""
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    # Try to determine vertical from the object
    vertical = 'general'
    if hasattr(instance.content_object, 'category'):
        vertical = getattr(instance.content_object.category, 'vertical', 'general')
    elif hasattr(instance.content_object, 'vertical'):
        vertical = instance.content_object.vertical
    
    return os.path.join('marketplace', vertical, str(instance.object_id), filename)

class Media(BaseModel):
    """Unified media handling for any listing type (Property, Vehicle, etc.)"""
    # Generic relation to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    file = models.FileField(upload_to=upload_to_marketplace)
    media_type = models.CharField(max_length=10, choices=(('image', 'Image'), ('video', 'Video')), default='image')
    
    is_main = models.BooleanField(default=False, help_text="Is this the primary cover image?")
    order = models.PositiveIntegerField(default=0)
    caption = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name_plural = "Media"
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"Media for {self.content_object}"
