from django_filters import rest_framework as filters
from django.db.models import Q
from .models import Listing
from catalog.models import Category

class ListingFilter(filters.FilterSet):
    min_price = filters.NumberFilter(field_name="price", lookup_expr='gte')
    max_price = filters.NumberFilter(field_name="price", lookup_expr='lte')
    exclude_vertical = filters.CharFilter(method='filter_exclude_vertical')

    def filter_exclude_vertical(self, queryset, name, value):
        """Exclude listings whose category has this vertical (e.g. property for marketplace-only UIs)."""
        if value:
            return queryset.exclude(category__vertical=value)
        return queryset
    
    # Custom filtering for JSON attributes
    # Example usage: ?attr__brand=Toyota&attr__year=2018
    # This requires custom logic in the ViewSet or a custom filter field
    
    class Meta:
        model = Listing
        fields = {
            'category': ['exact'],
            'status': ['exact'],
            'listing_type': ['exact'],
            'condition': ['exact'],
            'city': ['icontains'],
        }

    @property
    def qs(self):
        parent = super().qs
        # Handle dynamic attribute filtering
        # We look for query params starting with 'attr__'
        params = self.request.query_params
        attr_filters = {}
        for key, value in params.items():
            if key.startswith('attr__'):
                attr_name = key.replace('attr__', '')
                attr_filters[f'attributes__{attr_name}'] = value
        
        if attr_filters:
            parent = parent.filter(**attr_filters)
        
        # Handle category filtering to include subcategories
        category_id = params.get('category')
        if category_id:
            try:
                category_id = int(category_id)
                # Get the category and all its descendants
                category = Category.objects.filter(id=category_id).first()
                if category:
                    # Get all descendant category IDs (including the category itself)
                    category_ids = self._get_all_descendant_ids(category)
                    # Filter by category or any of its subcategories
                    parent = parent.filter(category_id__in=category_ids)
            except (ValueError, TypeError):
                # If category_id is not a valid integer, use exact match
                pass
        
        return parent
    
    def _get_all_descendant_ids(self, category):
        """Get all descendant category IDs including the category itself."""
        category_ids = [category.id]
        visited = {category.id}
        
        # Use a queue for iterative traversal
        queue = list(category.children.filter(is_active=True))
        
        while queue:
            current = queue.pop(0)
            if current.id in visited:
                continue
            visited.add(current.id)
            category_ids.append(current.id)
            # Add children to queue
            queue.extend(list(current.children.filter(is_active=True)))
        
        return category_ids