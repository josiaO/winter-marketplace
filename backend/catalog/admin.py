from django.contrib import admin
from .models import Category, CategoryField
from .services import CatalogService


class CategoryFieldInline(admin.TabularInline):
    """Inline admin for CategoryField within Category admin."""
    model = CategoryField
    extra = 1
    fields = (
        'field_label', 'field_name', 'field_type', 'required',
        'choices', 'unit', 'order'
    )
    ordering = ('order', 'field_label')

    def get_queryset(self, request):
        """Only show fields for subcategories."""
        qs = super().get_queryset(request)
        return qs

    def has_add_permission(self, request, obj=None):
        """Only allow adding fields to subcategories."""
        if obj is None:
            return True
        # Only allow adding fields if this is a subcategory
        return obj.parent_id is not None

    def has_change_permission(self, request, obj=None):
        """Only allow changing fields for subcategories."""
        if obj is None:
            return True
        return obj.parent_id is not None


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for Category model."""
    list_display = (
        'name', 'slug', 'vertical', 'parent', 'is_active',
        'order', 'field_count', 'created_at'
    )
    list_select_related = ('parent',)
    list_filter = (
        'vertical', 'is_active', 'is_service', 'is_physical',
        'parent', 'created_at'
    )
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'icon')
        }),
        ('Hierarchy', {
            'fields': ('parent', 'vertical', 'order')
        }),
        ('Category Type', {
            'fields': ('is_service', 'is_physical', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [CategoryFieldInline]

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
        CatalogService.invalidate_category_detail_cache(obj)

    def delete_model(self, request, obj):
        CatalogService.invalidate_category_detail_cache(obj)
        super().delete_model(request, obj)

    def get_inline_instances(self, request, obj=None):
        """Only show CategoryFieldInline for subcategories."""
        inlines = []
        # Only show field inline if this is a subcategory (has a parent)
        if obj and obj.parent_id is not None:
            # Get the inline instance
            inline = CategoryFieldInline(self.model, self.admin_site)
            if inline.has_add_permission(request, obj):
                inlines.append(inline)
        return inlines

    def field_count(self, obj):
        """Display the number of fields for this category."""
        # Only show field count for subcategories
        if obj.parent_id is None:
            return 'N/A (Main Category)'
        return obj.fields.count()
    field_count.short_description = 'Fields'


@admin.register(CategoryField)
class CategoryFieldAdmin(admin.ModelAdmin):
    """Admin interface for CategoryField model."""
    list_display = (
        'field_label', 'field_name', 'category', 'field_type',
        'required', 'order', 'created_at'
    )
    list_filter = (
        'field_type', 'required', 'category', 'category__vertical',
        'created_at'
    )
    search_fields = ('field_label', 'field_name', 'category__name')
    ordering = ('category', 'order', 'field_label')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': (
                'category', 'field_label', 'field_name', 'field_type',
                'required', 'order'
            )
        }),
        ('Field Configuration', {
            'fields': ('choices', 'unit'),
            'description': (
                'For select/enum fields, provide choices as a JSON array. '
                'For other fields, unit is optional.'
            )
        }),
        ('Legacy Fields (Auto-synced)', {
            'fields': ('name', 'key', 'options'),
            'classes': ('collapse',),
            'description': (
                'These fields are kept in sync with the universal fields '
                'above for backward compatibility.'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related for category."""
        qs = super().get_queryset(request)
        return qs.select_related('category')
