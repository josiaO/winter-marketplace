from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from django.core.cache import cache
from django.conf import settings
from core.permissions import IsAdmin, IsAdminOrReadOnly
from .models import Category, CategoryField, Attribute
from .serializers import (
    CategorySerializer, CategoryListSerializer, 
    CategoryFieldSerializer, AttributeSerializer
)
from .services import CatalogService, CACHE_TIMEOUT


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for Category with nested fields endpoint and aggressive caching for scale."""
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    
    def get_queryset(self):
        """Return queryset - include inactive for admins, only active for others."""
        queryset = Category.objects.all().prefetch_related('fields', 'children')
        # For non-admin users, only show active categories
        if not (self.request.user.is_authenticated and (self.request.user.is_superuser or self.request.user.is_staff)):
            queryset = queryset.filter(is_active=True)
        return queryset
    
    def get_tree_queryset(self):
        """Get only root categories (no parent) for tree structure."""
        queryset = self.get_queryset().filter(parent__isnull=True)
        return queryset
    
    def get_permissions(self):
        """Allow read for anyone, write only for admins."""
        if self.action in ['list', 'retrieve', 'fields', 'attributes', 'subcategories']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]
    
    def get_object(self):
        """
        Override to support both ID and slug lookups.
        """
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        
        if lookup_value is None:
            raise NotFound('Category not found.')
        
        queryset = self.get_queryset()
        
        try:
            category_id = int(lookup_value)
            try:
                return queryset.get(id=category_id)
            except Category.DoesNotExist:
                raise NotFound('Category not found.')
        except (ValueError, TypeError):
            try:
                return queryset.get(slug=lookup_value)
            except Category.DoesNotExist:
                raise NotFound('Category not found.')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return_tree = self.request.query_params.get('tree', 'false').lower() == 'true'
            if return_tree:
                return CategorySerializer
            return CategoryListSerializer
        return CategorySerializer
        
    def list(self, request, *args, **kwargs):
        """Override list to return hierarchical tree structure with caching."""
        return_tree = request.query_params.get('tree', 'false').lower() == 'true'
        
        if return_tree:
            cache_key = 'catalog_category_tree'
            bypass_cache = request.query_params.get('nocache', 'false').lower() == 'true'
            cached_data = None if bypass_cache else cache.get(cache_key)
            
            if cached_data is not None:
                return Response(cached_data)
            
            all_categories = self.get_queryset().order_by('order', 'name')
            category_map = {cat.id: CategorySerializer(cat, context={'request': request, 'skip_children': True}).data for cat in all_categories}
            tree = []
            
            for cat_id in category_map:
                category_map[cat_id]['children'] = []
            
            for cat in all_categories:
                serialized = category_map[cat.id]
                if cat.parent_id:
                    if cat.parent_id in category_map:
                        category_map[cat.parent_id]['children'].append(serialized)
                else:
                    tree.append(serialized)
            
            if not bypass_cache:
                cache.set(cache_key, tree, CACHE_TIMEOUT)
            return Response(tree)
        else:
            cache_key = 'catalog_category_list'
            cached_data = cache.get(cache_key)
            
            if cached_data is not None:
                return Response(cached_data)
                
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True)
            cache.set(cache_key, serializer.data, CACHE_TIMEOUT)
            return Response(serializer.data)
        
    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to cache individual categories."""
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        cache_key = f'catalog_category_detail_{lookup_value}'
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return Response(cached_data)
            
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        cache.set(cache_key, serializer.data, CACHE_TIMEOUT)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        CatalogService.invalidate_category_cache()
        return response
    
    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        slug = self.kwargs.get(self.lookup_field)
        category = Category.objects.filter(slug=slug).first()
        if category:
            CatalogService.invalidate_category_detail_cache(category)
        return response
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        CatalogService.invalidate_category_detail_cache(instance)
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['get'], url_path='fields')
    def fields(self, request, **kwargs):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        cache_key = f'catalog_category_fields_{lookup_value}'
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return Response(cached_data)
            
        category = self.get_object()
        fields = category.fields.all()
        serializer = CategoryFieldSerializer(fields, many=True)
        cache.set(cache_key, serializer.data, CACHE_TIMEOUT)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='attributes')
    def attributes(self, request, **kwargs):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        cache_key = f'catalog_category_attributes_detail_{lookup_value}'
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            return Response(cached_data)
            
        category = self.get_object()
        attributes = category.attributes.all().prefetch_related('options')
        serializer = AttributeSerializer(attributes, many=True)
        cache.set(cache_key, serializer.data, CACHE_TIMEOUT)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='subcategories')
    def subcategories(self, request):
        queryset = self.get_queryset().filter(parent__isnull=False)
        serializer = CategoryListSerializer(queryset, many=True)
        return Response(serializer.data)


class CategoryFieldViewSet(viewsets.ModelViewSet):
    serializer_class = CategoryFieldSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None
    
    def get_queryset(self):
        queryset = CategoryField.objects.all().select_related('category')
        category_id = self.request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        return queryset.order_by('category', 'order', 'field_label')
    
    def perform_create(self, serializer):
        field_data = serializer.validated_data
        field = CatalogService.create_category_field(**field_data)
        serializer.instance = field
    
    def perform_update(self, serializer):
        field = self.get_object()
        field_data = serializer.validated_data
        CatalogService.update_category_field(field, **field_data)
    
    def perform_destroy(self, instance):
        CatalogService.delete_category_field(instance)