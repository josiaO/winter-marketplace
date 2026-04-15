import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, viewsets, filters, status, throttling
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample, inline_serializer
from django_filters.rest_framework import DjangoFilterBackend

from marketplace.models import MarketplaceItem
from marketplace.serializers import MarketplaceItemSerializer

from .models import Listing, ListingLike, ListingMedia
from .serializers import ListingSerializer, ListingDetailSerializer
from .filters import ListingFilter
from . import services as listing_svc
from .validators import validate_media_file
from accounts.permissions import IsAgent, IsSeller, IsAdmin
from core.drf_utils import viewset_mapped_action
from .services.search_service import unified_listing_search
from .services.management_service import toggle_listing_verification, toggle_listing_featured

logger = logging.getLogger(__name__)


class ListingAnonRateThrottle(throttling.AnonRateThrottle):
    scope = 'listing_list_anon'


class ListingUserRateThrottle(throttling.UserRateThrottle):
    scope = 'listing_list_user'


class ListingViewSet(viewsets.ModelViewSet):
    queryset = Listing.objects.filter(is_published=True)
    serializer_class = ListingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ListingFilter 
    
    # Conditional search fields for Postgres full text search
    if 'postgresql' in settings.DATABASES['default']['ENGINE']:
        search_fields = ['@title', '@description', '@city', '@address']
    else:
        search_fields = ['title', 'description', 'city', 'address']
    ordering_fields = ['price', 'created_at', 'view_count']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ListingDetailSerializer
        return ListingSerializer

    def get_throttles(self):
        """Restore rate limiting for public listing endpoints (list, retrieve) with specific rates."""
        if self.action in ['list', 'retrieve']:
            return [ListingAnonRateThrottle(), ListingUserRateThrottle()]
        return super().get_throttles()  # Apply default rate limiting for create/update/delete

    def get_authenticators(self):
        if viewset_mapped_action(self) in ('list', 'retrieve'):
            return []
        return super().get_authenticators()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action == 'seller':
            # Allow any authenticated user to access their own listings
            return [permissions.IsAuthenticated()]
        # Allow both Agents and Sellers
        return [permissions.IsAuthenticated(), (IsAgent | IsSeller)()]

    def list(self, request, *args, **kwargs):
        """Override list to ensure request context is passed for media URLs."""
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    def get_queryset(self):
        """Filter listings based on user role and query params."""
        if getattr(self, 'swagger_fake_view', False):
            return Listing.objects.none()
        queryset = Listing.objects.all()
        user = self.request.user
        
        # Optimize queryset with select_related
        queryset = queryset.select_related(
            'owner',
            'owner__seller_profile',
            'owner__profile',
            'owner__trust_score',
            'category',
            'store',
            'marketplaceitem',
        ).prefetch_related('media', 'likes')
        
        if user.is_authenticated:
            is_admin = user.is_superuser or user.is_staff
            owner_filter = self.request.query_params.get('owner', None)
            
            # Admins see everything unless they specifically filter for 'me'
            if is_admin and owner_filter != 'me':
                return queryset
            
            # If requesting own listings
            if owner_filter == 'me' or owner_filter == str(user.id):
                queryset = queryset.filter(owner=user)
            # For list action, show published listings to public
            elif self.action == 'list':
                queryset = queryset.filter(
                    is_published=True,
                    owner__isnull=False,
                    owner__is_active=True
                )
                # Filter out inactive seller profiles/stores
                queryset = queryset.filter(
                    Q(owner__seller_profile__isnull=True) | Q(owner__seller_profile__is_active=True)
                ).filter(
                    Q(store__isnull=True) | Q(store__is_active=True)
                )
        else:
            # Anonymous users only see published items from active owners/stores
            queryset = queryset.filter(
                is_published=True,
                owner__isnull=False,
                owner__is_active=True
            ).filter(
                Q(owner__seller_profile__isnull=True) | Q(owner__seller_profile__is_active=True)
            ).filter(
                Q(store__isnull=True) | Q(store__is_active=True)
            )
        
        return queryset

    def create(self, request, *args, **kwargs):
        """Thinner create method delegating media handling to service."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                listing = serializer.save(owner=self.request.user)
                # Delegate media handling
                media_files = request.FILES.getlist('media')
                if media_files:
                    saved_count = listing_svc.handle_listing_media(listing, media_files)
                    logger.info(f"Successfully saved {saved_count}/{len(media_files)} media files for listing {listing.id}")
            
            # Refresh and return
            listing.refresh_from_db()
            response_serializer = self.get_serializer(listing, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Unexpected error creating listing: {str(e)}", exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def update(self, request, *args, **kwargs):
        """Thinner update method delegating media handling to service."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                listing = serializer.save()
                # Handle media files - append new media
                media_files = request.FILES.getlist('media')
                if media_files:
                    saved_count = listing_svc.handle_listing_media(listing, media_files, append=True)
                    logger.info(f"Successfully saved {saved_count}/{len(media_files)} new media files for listing {listing.id}")
            
            # Refresh and return
            listing.refresh_from_db()
            response_serializer = self.get_serializer(listing, context={'request': request})
            return Response(response_serializer.data)
        except Exception as e:
            logger.error(f"Unexpected error updating listing: {str(e)}", exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, *args, **kwargs):
        # Get object with optimized queryset to ensure relationships are loaded
        # This is critical for is_ghost_listing property to work correctly
        # Allow retrieving ghost listings (deleted/deactivated sellers) for display purposes
        # but they will show as unavailable
        queryset = Listing.objects.all().select_related(
            'owner',
            'owner__seller_profile',
            'owner__profile',
            'category',
            'store'
        ).prefetch_related('media', 'likes')
        
        try:
            instance = queryset.get(pk=kwargs['pk'])
        except Listing.DoesNotExist:
            return Response(
                {'detail': 'Listing not found.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Increment views on retrieve (only if listing is not a ghost listing)
        if not instance.is_ghost_listing:
            listing_svc.increment_views(
                instance, 
                user=request.user, 
                ip_address=request.META.get('REMOTE_ADDR')
            )
        # Ensure request context is passed for media URL generation
        serializer = self.get_serializer(instance, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def like(self, request, pk=None):
        listing = self.get_object()
        like, created = ListingLike.objects.get_or_create(listing=listing, user=request.user)
        if not created:
            like.delete()
            return Response({'status': 'unliked'}, status=status.HTTP_200_OK)
        return Response({'status': 'liked'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def toggle_verified(self, request, pk=None):
        """Toggle verification status of a listing (Admin only)"""
        listing = self.get_object()
        listing = toggle_listing_verification(listing)
        return Response({
            'status': 'verified' if listing.is_verified else 'unverified',
            'is_verified': listing.is_verified,
            'verified_at': listing.verified_at
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def toggle_featured(self, request, pk=None):
        """Toggle featured status of a listing (Admin only)"""
        listing = self.get_object()
        listing = toggle_listing_featured(listing)
        return Response({
            'status': 'featured' if listing.is_featured else 'unfeatured',
            'is_featured': listing.is_featured,
            'featured_at': listing.featured_at
        })

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def seller(self, request):
        """Get listings for the authenticated seller."""
        # Allow any authenticated user to see their own listings
        # Don't filter by is_published for seller's own listings
        queryset = Listing.objects.filter(owner=request.user)
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        published_filter = request.query_params.get('published')
        if published_filter is not None:
            is_published = published_filter.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(is_published=is_published)
        
        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True, context={'request': request})
        return Response({
            'results': serializer.data,
            'count': queryset.count()
        })

class UnifiedListingView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(
        parameters=[
            OpenApiParameter("q", OpenApiTypes.STR, description="Search query"),
            OpenApiParameter("city", OpenApiTypes.STR, description="Filter by city"),
            OpenApiParameter("min_price", OpenApiTypes.FLOAT, description="Minimum price"),
            OpenApiParameter("max_price", OpenApiTypes.FLOAT, description="Maximum price"),
        ],
        responses={
            200: inline_serializer("UnifiedSearchResponse", fields={
                "marketplace_items": MarketplaceItemSerializer(many=True)
            })
        }
    )
    def get(self, request):
        query = request.query_params.get('q', '')
        city = request.query_params.get('city', None)
        min_price = request.query_params.get('min_price', None)
        max_price = request.query_params.get('max_price', None)

        items = unified_listing_search(
            query=query, 
            city=city, 
            min_price=min_price, 
            max_price=max_price
        )

        return Response({
            'marketplace_items': MarketplaceItemSerializer(items, many=True, context={'request': request}).data,
        })
