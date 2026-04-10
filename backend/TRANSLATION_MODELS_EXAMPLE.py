"""
Example: How to update models for translation support.

IMPORTANT: These changes require database migrations.
Run: python manage.py makemigrations && python manage.py migrate

1. Update catalog/models.py Category model:
"""

from parler.models import TranslatableModel, TranslatedFields
from django.db import models

# BEFORE:
# class Category(BaseModel):
#     name = models.CharField(max_length=100)
#     description = models.TextField(blank=True)

# AFTER:
class Category(TranslatableModel, BaseModel):
    """Hierarchical category system with translations."""
    # Non-translatable fields stay the same
    slug = models.SlugField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    vertical = models.CharField(max_length=20, choices=VERTICAL_CHOICES, default='other', db_index=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    
    # Translatable fields
    translations = TranslatedFields(
        name=models.CharField(max_length=100),
        description=models.TextField(blank=True),
    )
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['vertical', 'order', 'name']


"""
2. Update core/models/listing.py BaseListing model:
"""

class BaseListing(TranslatableModel, BaseModel):
    """Abstract base model with translations."""
    # Non-translatable fields
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, ...)
    category = models.ForeignKey('catalog.Category', ...)
    price = models.DecimalField(...)
    currency = models.CharField(max_length=3, default='TZS')
    # ... other non-translatable fields
    
    # Translatable fields
    translations = TranslatedFields(
        title=models.CharField(max_length=200, db_index=True),
        description=models.TextField(blank=True),
    )
    
    class Meta:
        abstract = True


"""
3. Update catalog/serializers.py to use TranslatableModelSerializer:
"""

from parler_rest.serializers import TranslatableModelSerializer
from parler_rest.fields import TranslatedFieldsField

class CategorySerializer(TranslatableModelSerializer):
    """Serializer with translation support."""
    translations = TranslatedFieldsField(shared_model=Category)
    
    class Meta:
        model = Category
        fields = [
            'id', 'translations', 'slug', 'icon', 'parent', 'vertical',
            'is_active', 'order', 'fields', 'attributes', 'children'
        ]


"""
4. In views, ensure language is set from Accept-Language header:
"""

from django.utils import translation
from django.utils.translation import get_language_from_request

class CategoryViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        # Set language from request
        language = get_language_from_request(self.request)
        translation.activate(language)
        return Category.objects.translated(language).all()
    
    def retrieve(self, request, *args, **kwargs):
        language = get_language_from_request(request)
        translation.activate(language)
        return super().retrieve(request, *args, **kwargs)
