from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from core.models.base import BaseModel

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
    
    # Universal catalog flags
    is_service = models.BooleanField(default=False, help_text="Is this a service category?")
    is_physical = models.BooleanField(default=True, help_text="Is this a physical product category?")
    
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    def is_leaf(self) -> bool:
        """Returns True if this category has no subcategories."""
        return not self.children.exists()

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['vertical', 'order', 'name']
        indexes = [
            models.Index(fields=['vertical', 'is_active']),
            models.Index(fields=['parent', 'is_active']),
        ]

    def __str__(self):
        # Access parent.name directly to avoid recursive __str__ calls
        # Check parent_id first to avoid unnecessary database queries
        if self.parent_id:
            try:
                # Directly access the name attribute to avoid calling parent's __str__
                parent_name = self.parent.name
                return f"{parent_name} > {self.name}"
            except (AttributeError, Category.DoesNotExist):
                # Fallback if parent doesn't exist or can't be accessed
                pass
        return f"[{self.get_vertical_display()}] {self.name}"

class CategoryField(BaseModel):
    """Defines dynamic specs for a category."""
    FIELD_TYPES = (
        ('text', _('Text')),
        ('long_text', _('Long Text')),
        ('integer', _('Integer')),
        ('decimal', _('Decimal')),
        ('number', _('Number (Legacy)')),
        ('select', _('Select')),
        ('boolean', _('Boolean')),
        ('date', _('Date')),
    )
    
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='fields')
    name = models.CharField(max_length=50)  # Human readable name (legacy, use field_label)
    key = models.SlugField(max_length=50)    # Internal key for spec JSON (legacy, use field_name)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='text')
    required = models.BooleanField(default=False)
    options = models.JSONField(null=True, blank=True, help_text="List of options for select fields (legacy)")
    unit = models.CharField(max_length=20, blank=True, help_text="e.g. GB, square meters, Liters")
    order = models.PositiveIntegerField(default=0)
    
    # Universal schema fields
    field_name = models.SlugField(max_length=50, blank=True, help_text="Internal key (synced from key)")
    field_label = models.CharField(max_length=100, blank=True, help_text="Human-readable label (synced from name)")
    choices = models.JSONField(null=True, blank=True, help_text="List of choices for enum/multi_enum fields")
    
    def clean(self):
        """Validate that fields can only be added to subcategories."""
        super().clean()
        if self.category and not self.category.parent_id:
            raise ValidationError(
                'Category fields can only be added to subcategories. '
                'Main categories (categories without a parent) cannot have fields.'
            )
    
    def save(self, *args, **kwargs):
        """Validate and save."""
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('category', 'key')
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.category.name} - {self.name} ({self.key})"


class Attribute(BaseModel):
    """Dynamic attributes for a category (e.g. Brand, RAM, Storage)."""
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SELECT = "select"

    FIELD_TYPES = [
        (TEXT, "Text"),
        (NUMBER, "Number"),
        (BOOLEAN, "Boolean"),
        (SELECT, "Select"),
    ]

    category = models.ForeignKey(
        Category,
        related_name="attributes",
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    key = models.SlugField(max_length=100, help_text="Internal key for attribute")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('category', 'key')
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.category.name} - {self.name}"


class AttributeOption(BaseModel):
    """Predefined options for 'select' type attributes."""
    attribute = models.ForeignKey(
        Attribute,
        related_name="options",
        on_delete=models.CASCADE
    )
    value = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'value']

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"
