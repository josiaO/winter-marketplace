from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Category, CategoryField, Attribute, AttributeOption


class CategoryFieldSerializer(serializers.ModelSerializer):
    """Serializer for CategoryField - defines dynamic specs for listings."""
    field_name = serializers.CharField(required=False, allow_blank=True)
    field_label = serializers.CharField(required=False, allow_blank=True)
    choices = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = CategoryField
        fields = [
            'id', 'category', 'field_name', 'field_label', 'field_type',
            'required', 'choices', 'unit', 'order'
        ]
        read_only_fields = ['id']

    def validate(self, data):
        """Check for field uniqueness within a category."""
        category = data.get('category')
        field_name = data.get('field_name')

        if not field_name:
            # Check context/initial_data for field_name if not in validated_data
            if 'field_name' in self.initial_data:
                field_name = self.initial_data['field_name']
        
        if category and field_name:
            # If updating, exclude self
            qs = CategoryField.objects.filter(category=category, key=field_name)
            if self.instance:
                qs = qs.exclude(id=self.instance.id)
            
            if qs.exists():
                raise serializers.ValidationError(
                    {"field_name": f"A field with the internal key '{field_name}' already exists in this category."}
                )
        return data

    def to_representation(self, instance):
        """Override to return field_name/field_label from model and handle choices fallback."""
        data = super().to_representation(instance)
        # Fallback choices/options synchronization
        choices = data.get('choices')
        options = getattr(instance, 'options', None)
        if not choices and options:
            data['choices'] = options
        
        data['field_name'] = instance.field_name or instance.key or ''
        data['field_label'] = instance.field_label or instance.name or ''
        return data


    def create(self, validated_data):
        """Create field and sync universal fields."""
        # Validate that category is a subcategory
        category = validated_data.get('category')
        if category and not category.parent_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(
                'Category fields can only be added to subcategories. '
                'Main categories cannot have fields.'
            )

        # Extract field_name, field_label, and choices
        field_name = validated_data.pop('field_name', None) or ''
        field_label = validated_data.pop('field_label', None) or ''
        choices_data = validated_data.get('choices', None)

        # Create the field with both legacy and universal fields
        # pylint: disable=no-member
        field = CategoryField.objects.create(
            key=field_name,
            name=field_label,
            field_name=field_name,
            field_label=field_label,
            **validated_data
        )

        # Force synchronize choices and options
        if choices_data is not None:
            field.choices = choices_data if isinstance(choices_data, list) else None
            field.options = field.choices
            field.save()

        return field

    def update(self, instance, validated_data):
        """Update field and sync universal fields."""
        # Extract field_name, field_label, and choices
        field_name = validated_data.pop('field_name', None)
        field_label = validated_data.pop('field_label', None)
        choices_data = validated_data.get('choices', None)

        # Update key/name if provided
        if field_name is not None:
            instance.key = field_name
            instance.field_name = field_name
        if field_label is not None:
            instance.name = field_label
            instance.field_label = field_label

        # Force synchronize choices and options
        if choices_data is not None:
            instance.choices = choices_data if isinstance(choices_data, list) else None
            instance.options = instance.choices

        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class AttributeOptionSerializer(serializers.ModelSerializer):
    """Serializer for AttributeOption."""
    class Meta:
        model = AttributeOption
        fields = ['id', 'value', 'order']


class AttributeSerializer(serializers.ModelSerializer):
    """Serializer for Attribute with nested options."""
    options = AttributeOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Attribute
        fields = [
            'id', 'category', 'name', 'key', 'field_type',
            'is_required', 'order', 'options'
        ]
        read_only_fields = ['id']


class CategoryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for category lists and subcategory display."""
    fields_count = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    is_leaf = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'vertical', 'icon',
            'is_active', 'is_service', 'is_physical', 'parent', 'parent_name',
            'is_leaf', 'fields_count', 'order'
        ]

    @extend_schema_field(serializers.BooleanField())
    def get_is_leaf(self, obj):
        return obj.is_leaf() if hasattr(obj, 'is_leaf') else False

    @extend_schema_field(serializers.IntegerField())
    def get_fields_count(self, obj):
        return obj.fields.count() if hasattr(obj, 'fields') else 0


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category with nested fields and children."""
    fields = CategoryFieldSerializer(many=True, read_only=True)
    attributes = AttributeSerializer(many=True, read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    children = serializers.SerializerMethodField()
    listing_count = serializers.SerializerMethodField()
    vertical = serializers.ChoiceField(
        choices=Category.VERTICAL_CHOICES,
        required=False,
        allow_blank=False
    )
    is_leaf = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'icon',
            'parent', 'parent_name', 'vertical',
            'is_active', 'is_service', 'is_physical',
            'order', 'fields', 'attributes', 'children', 'listing_count', 'is_leaf'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    @extend_schema_field(serializers.BooleanField())
    def get_is_leaf(self, obj):
        return obj.is_leaf() if hasattr(obj, 'is_leaf') else False

    def validate_slug(self, value):
        """Validate slug is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError('Slug cannot be empty.')
        return value.strip()

    def validate(self, data):
        """
        Validate category data and auto-inherit vertical from parent.
        """
        parent = data.get('parent')
        vertical = data.get('vertical')

        if parent is not None:
            parent_id = parent.pk if hasattr(parent, 'pk') else parent
            instance_id = self.instance.pk if self.instance else None
            if instance_id and parent_id == instance_id:
                raise serializers.ValidationError(
                    {'parent': 'A category cannot be its own parent.'}
                )

        # If creating a subcategory, inherit vertical from parent
        if parent and not vertical:
            # Parent might be an integer ID or a Category instance
            if isinstance(parent, (int, str)):
                try:
                    # pylint: disable=no-member
                    parent_obj = Category.objects.get(pk=parent)
                    data['vertical'] = parent_obj.vertical
                except Category.DoesNotExist as exc:
                    raise serializers.ValidationError(
                        {'parent': 'Parent category does not exist.'}
                    ) from exc
            elif hasattr(parent, 'vertical'):
                # Parent is already a Category instance
                data['vertical'] = parent.vertical

        # If no parent and no vertical, use default
        if not parent and not vertical:
            data['vertical'] = 'other'

        return data

    def create(self, validated_data):
        """
        Create category and ensure subcategories inherit vertical.
        """
        parent = validated_data.get('parent')
        vertical = validated_data.get('vertical')

        # If creating a subcategory, inherit vertical from parent
        if parent and not vertical:
            # Get parent object if it's an ID
            if isinstance(parent, (int, str)):
                # pylint: disable=no-member
                parent_obj = Category.objects.get(pk=parent)
                validated_data['vertical'] = parent_obj.vertical
            elif hasattr(parent, 'vertical'):
                validated_data['vertical'] = parent.vertical

        return super().create(validated_data)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_children(self, obj):
        """Serialize children categories - show ALL children for admin visibility with nested children."""
        # Check context to avoid recursion when tree is built manually in view
        if self.context.get('skip_children'):
            return []

        # Show all children (active and inactive) for admin management
        # In the frontend, active/inactive status is shown with a badge
        request = self.context.get('request')
        is_admin = (
            request and request.user.is_authenticated and
            (request.user.is_superuser or request.user.is_staff)
        )
        if is_admin:
            children = obj.children.all().order_by('order', 'name')
        else:
            children = obj.children.filter(is_active=True).order_by('order', 'name')
        # Use CategorySerializer recursively to include nested children
        return CategorySerializer(children, many=True, context=self.context).data

    @extend_schema_field(serializers.IntegerField())
    def get_listing_count(self, obj):
        """Get count of listings in this category (including children), with caching."""
        from django.core.cache import cache
        cache_key = f"cat_listing_count_{obj.id}"
        cached_count = cache.get(cache_key)
        if cached_count is not None:
            return cached_count

        from listings.models import Listing
        # Count listings in this category and all its descendants
        category_ids = self._get_all_descendant_ids(obj)
        count = Listing.objects.filter(
            category_id__in=category_ids,
            is_published=True,
            status='active'
        ).count()
        
        # Cache for 5 minutes
        cache.set(cache_key, count, 300)
        return count

    def _get_all_descendant_ids(self, category):
        """
        Get all descendant category IDs using iterative approach.
        Uses prefetched children to avoid N+1 queries.
        """
        category_ids = [category.id]
        visited = {category.id}
        
        # Use queue for BFS
        # Use .all() to benefit from prefetch_related('children')
        children = list(category.children.all())
        queue = [c for c in children if c.is_active]

        while queue:
            current = queue.pop(0)
            if current.id in visited:
                continue
            visited.add(current.id)
            category_ids.append(current.id)
            
            # Add its children to queue using prefetched .all()
            for child in current.children.all():
                if child.is_active and child.id not in visited:
                    queue.append(child)

        return category_ids
