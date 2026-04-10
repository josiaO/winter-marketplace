"""
DEPRECATED: legacy ``core.Category`` table.

Listings and commerce use **catalog.Category** (`catalog.models.Category`).
This model remains for one-off scripts (e.g. ``seed_marketplace.py``) until migrated off.
Do not use in new code.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from .base import BaseModel

class Category(BaseModel):
    """Hierarchical category system for marketplace scalability."""
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon name (e.g. FontAwesome or Material Icon)")
    
    parent = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='children'
    )
    
    # Marketplace Type (to distinguish between main verticals)
    VERTICAL_CHOICES = (
        ('property', _('Real Estate')),
        ('vehicle', _('Vehicles')),
        ('electronics', _('Electronics')),
        ('fashion', _('Fashion')),
        ('other', _('Other')),
    )
    vertical = models.CharField(max_length=20, choices=VERTICAL_CHOICES, default='other', db_index=True)
    
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['vertical', 'order', 'name']

    def __str__(self):
        if self.parent:
            return f"{self.parent} > {self.name}"
        return f"[{self.get_vertical_display()}] {self.name}"
