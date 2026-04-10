"""
Catalog Services: Manage taxonomy, categories, and dynamic fields.
Ensures thin views/models and centralized cache invalidation.
"""
import logging
from django.core.cache import cache
from django.conf import settings
from .models import Category, CategoryField

logger = logging.getLogger(__name__)

# Define cache timeout for catalog (1 hour default)
CACHE_TIMEOUT = getattr(settings, 'CATALOG_CACHE_TIMEOUT', 60 * 60)

class CatalogService:
    @staticmethod
    def invalidate_category_cache():
        """Invalidate all category-related cache keys."""
        cache.delete('catalog_category_list')
        cache.delete('catalog_category_tree')
        logger.debug("Catalog category cache invalidated.")

    @staticmethod
    def invalidate_category_detail_cache(category):
        """Invalidate specific category and its field caches."""
        if not category:
            return
        
        # Invalidate both ID and slug based caches
        cache_keys = [
            f'catalog_category_detail_{category.id}',
            f'catalog_category_detail_{category.slug}',
            f'catalog_category_fields_{category.id}',
            f'catalog_category_fields_{category.slug}',
            f'catalog_category_attributes_detail_{category.id}',
            f'catalog_category_attributes_detail_{category.slug}',
        ]
        for key in cache_keys:
            cache.delete(key)
        
        # Also clear global list/tree
        CatalogService.invalidate_category_cache()

    @staticmethod
    def sync_category_field(field: CategoryField) -> CategoryField:
        """
        Synchronize legacy fields (key, name, options) with new 
        universal schema (field_name, field_label, choices).
        """
        modified = False
        
        # Sync Internal Keys (key <-> field_name)
        if not field.field_name and field.key:
            field.field_name = field.key
            modified = True
        elif not field.key and field.field_name:
            field.key = field.field_name
            modified = True
            
        # Sync Human-readable Labels (name <-> field_label)
        if not field.field_label and field.name:
            field.field_label = field.name
            modified = True
        elif not field.name and field.field_label:
            field.name = field.field_label
            modified = True
            
        # Sync Choices (options <-> choices)
        if not field.choices and field.options:
            field.choices = field.options
            modified = True
            
        if modified:
            field.save(update_fields=['field_name', 'key', 'field_label', 'name', 'choices', 'updated_at'])
            
        return field

    @classmethod
    def create_category_field(cls, **data) -> CategoryField:
        """Centralized creation for category fields with auto-sync."""
        field = CategoryField.objects.create(**data)
        cls.sync_category_field(field)
        cls.invalidate_category_detail_cache(field.category)
        return field

    @classmethod
    def update_category_field(cls, field: CategoryField, **data) -> CategoryField:
        """Centralized update for category fields with auto-sync."""
        for key, value in data.items():
            setattr(field, key, value)
        field.save()
        cls.sync_category_field(field)
        cls.invalidate_category_detail_cache(field.category)
        return field

    @classmethod
    def delete_category_field(cls, field: CategoryField) -> None:
        """Centralized deletion for category fields."""
        category = field.category
        field.delete()
        cls.invalidate_category_detail_cache(category)
