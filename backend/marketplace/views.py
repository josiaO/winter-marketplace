from django.db.models import Q, Exists, OuterRef, Value, BooleanField
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, filters, status, serializers
from rest_framework.decorators import action, api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample, inline_serializer
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.pagination import PageNumberPagination

from .models import MarketplaceItem, SellerProfile, Store, StoreFollow, SellerPaymentMethod
from .serializers import (
    MarketplaceItemSerializer, SellerProfileSerializer,
    StoreSerializer, SellerPaymentMethodSerializer
)
from marketplace.services.seller_service import SellerService, get_seller_review_stats, toggle_store_follow
from listings.models import ListingLike, Listing
from listings.serializers import ListingSerializer
from accounts.permissions import IsAgent, IsSeller
from trust.models import Review
from trust.serializers import ReviewSerializer


def _public_seller_visibility_q() -> Q:
    """Buyers may only see sellers that are verified and active on the storefront."""
    return Q(is_verified=True, is_active=True)


class SellerPaymentMethodViewSet(viewsets.ModelViewSet):
    """
    API endpoint for seller payment methods.
    """
    serializer_class = SellerPaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated, IsSeller]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SellerPaymentMethod.objects.none()
        return SellerPaymentMethod.objects.filter(seller__user=self.request.user)

    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'seller_profile'):
            raise serializers.ValidationError({"detail": "You must have a seller profile first."})
        serializer.save(seller=self.request.user.seller_profile)


class MarketplaceItemViewSet(viewsets.ModelViewSet):
    queryset = MarketplaceItem.objects.filter(is_published=True)
    serializer_class = MarketplaceItemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'status', 'listing_type', 'condition', 'city']
    search_fields = ['title', 'description', 'city', 'address']
    ordering_fields = ['price', 'created_at', 'view_count']
    
    def get_queryset(self):
        """Filter marketplace items to exclude ghost listings (inactive/deleted sellers)."""
        if getattr(self, 'swagger_fake_view', False):
            return MarketplaceItem.objects.none()
        queryset = MarketplaceItem.objects.all().select_related(
            'owner',
            'owner__seller_profile',
            'owner__profile',
            'category',
            'store'
        ).prefetch_related(
            'media',
            'likes',
            'attribute_values',
            'attribute_values__attribute',
            'attribute_values__value_option',
        )
        
        user = self.request.user
        if user.is_authenticated:
            owner_filter = self.request.query_params.get('owner', None)
            if owner_filter == 'me' or owner_filter == str(user.id):
                return queryset.filter(owner=user)
            # Detail / write: owner must access drafts; everyone else only sees public items
            if self.action in ('retrieve', 'update', 'partial_update', 'destroy'):
                public_ok = (
                    Q(is_published=True)
                    & Q(owner__isnull=False)
                    & Q(owner__is_active=True)
                    & (
                        Q(owner__seller_profile__isnull=True)
                        | Q(owner__seller_profile__is_active=True)
                    )
                    & (Q(store__isnull=True) | Q(store__is_active=True))
                )
                return queryset.filter(Q(owner=user) | public_ok)

        # Public list (and anonymous): published only
        queryset = queryset.filter(is_published=True)
        # 2. Exclude missing owners
        queryset = queryset.filter(owner__isnull=False)
        # 3. Exclude inactive owners
        queryset = queryset.filter(owner__is_active=True)
        # 4. Exclude inactive seller profiles
        queryset = queryset.filter(
            Q(owner__seller_profile__isnull=True) |
            Q(owner__seller_profile__is_active=True)
        )
        # 5. Exclude inactive stores
        queryset = queryset.filter(
            Q(store__isnull=True) | Q(store__is_active=True)
        )
        
        return queryset

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        # Allow both Agents and Sellers
        return [permissions.IsAuthenticated(), (IsAgent | IsSeller)()]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class SellerProfileViewSet(viewsets.ModelViewSet):
    """
    API endpoint for seller profiles.
    """
    queryset = SellerProfile.objects.all()
    serializer_class = SellerProfileSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['business_name', 'user__username', 'user__email']
    ordering_fields = ['created_at', 'average_rating', 'is_verified']
    filterset_fields = ['is_verified', 'is_active', 'business_type']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action in ['verify', 'unverify']:
            return [permissions.IsAuthenticated(), IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SellerProfile.objects.none()
        queryset = SellerProfile.objects.select_related('user').all()
        user = self.request.user
        vis = _public_seller_visibility_q()

        if self.action == 'retrieve':
            if user.is_staff:
                return queryset
            if not user.is_authenticated:
                return queryset.filter(vis)
            return queryset.filter(Q(user=user) | vis)

        if not user.is_staff:
            if self.action == 'list':
                if user.is_authenticated:
                    queryset = queryset.filter(vis | Q(user=user))
                else:
                    queryset = queryset.filter(vis)
            elif self.action in ['update', 'partial_update', 'upload_documents']:
                if user.is_authenticated:
                    queryset = queryset.filter(user=user)
                else:
                    queryset = queryset.none()

        return queryset

    def perform_create(self, serializer):
        if hasattr(self.request.user, 'seller_profile'):
            raise serializers.ValidationError({"detail": "User already has a seller profile."})
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def verify(self, request, pk=None):
        """Verify a seller (admin only)."""
        seller = self.get_object()
        SellerService.verify_by_admin(seller)
        seller.refresh_from_db()
        serializer = self.get_serializer(seller)
        return Response({
            'message': f'Seller {seller.user.username} has been verified',
            'seller': serializer.data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def unverify(self, request, pk=None):
        """Unverify a seller (admin only)."""
        seller = self.get_object()
        SellerService.unverify_by_admin(seller)
        seller.refresh_from_db()
        serializer = self.get_serializer(seller)
        return Response({
            'message': f'Seller {seller.user.username} has been unverified',
            'seller': serializer.data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def upload_documents(self, request, pk=None):
        """Upload verification documents (seller can upload their own documents)."""
        seller = self.get_object()
        
        # Check if user owns this seller profile or is admin
        if seller.user != request.user and not request.user.is_staff:
            return Response(
                {'error': 'You can only upload documents for your own seller profile'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get uploaded files
        files = request.FILES.getlist('documents')
        if not files:
            return Response(
                {'error': 'No documents provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            uploaded_urls = SellerService.apply_after_document_upload(seller, files)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        seller.refresh_from_db()
        serializer = self.get_serializer(seller)
        return Response({
            'message': f'{len(uploaded_urls)} document(s) uploaded successfully',
            'seller': serializer.data
        })

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def reviews(self, request, pk=None):
        """
        Get reviews for a seller.
        GET /api/v1/marketplace/seller-profiles/{id}/reviews/
        """
        seller_profile = self.get_object()
        stats = get_seller_review_stats(seller_profile, user=request.user)
        queryset = stats['queryset']
        
        # Get paginated reviews
        paginator = PageNumberPagination()
        paginator.page_size = 20
        
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            reviews_serializer = ReviewSerializer(page, many=True)
            return paginator.get_paginated_response({
                'average_rating': stats['average_rating'],
                'total_reviews': stats['total_reviews'],
                'rating_distribution': stats['rating_distribution'],
                'reviews': reviews_serializer.data
            })
        
        reviews_serializer = ReviewSerializer(queryset, many=True)
        return Response({
            'average_rating': stats['average_rating'],
            'total_reviews': stats['total_reviews'],
            'rating_distribution': stats['rating_distribution'],
            'reviews': reviews_serializer.data
        })


class StoreViewSet(viewsets.ModelViewSet):
    """
    API endpoint for storefronts.
    """
    serializer_class = StoreSerializer
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_featured']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'total_followers', 'total_sales']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Store.objects.none()
        qs = Store.objects.filter(is_active=True).select_related('seller', 'seller__user')
        user = self.request.user
        if user.is_authenticated:
            return qs.annotate(
                is_followed=Exists(
                    StoreFollow.objects.filter(store_id=OuterRef('pk'), user_id=user.id)
                )
            )
        return qs.annotate(is_followed=Value(False, output_field=BooleanField()))

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        if not hasattr(self.request.user, 'seller_profile'):
            raise serializers.ValidationError({"detail": "You must create a seller profile first."})
        store = serializer.save(seller=self.request.user.seller_profile)
        from marketplace.services.store_service import sync_store_from_seller_profile

        sync_store_from_seller_profile(store.seller)
        return store

    @action(detail=True, methods=['post'])
    def follow(self, request, slug=None):
        store = self.get_object()
        toggle_store_follow(request.user, store, follow=True)
        return Response({'status': 'followed'})

    @action(detail=True, methods=['post'])
    def unfollow(self, request, slug=None):
        store = self.get_object()
        toggle_store_follow(request.user, store, follow=False)
        return Response({'status': 'unfollowed'})


@extend_schema(
    request=inline_serializer("FavoritesAddRequest", fields={
        "listingId": serializers.CharField(required=False),
        "listing": serializers.CharField(required=False),
    }),
    responses={
        200: inline_serializer("FavoritesListResponse", fields={
            "favorites": inline_serializer("FavoriteItem", fields={
                "id": serializers.CharField(),
                "listing": ListingSerializer()
            }, many=True)
        })
    }
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def favorites_list_add(request):
    """Get all listings favorited by the current user or add a listing to favorites."""
    if request.method == 'GET':
        likes = (
            ListingLike.objects.filter(user=request.user)
            .select_related('listing', 'listing__category', 'listing__owner')
            .prefetch_related('listing__media')
            .order_by('-created_at')
        )
        favorites = []
        for like in likes:
            if like.listing and like.listing.is_published:
                serializer = ListingSerializer(like.listing, context={'request': request})
                favorites.append({
                    'id': str(like.id),
                    'listing': serializer.data
                })
        return Response({'favorites': favorites})
    
    elif request.method == 'POST':
        listing_id = request.data.get('listingId') or request.data.get('listing')
        if not listing_id:
            return Response({'error': 'listingId or listing is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            listing = Listing.objects.get(id=listing_id, is_published=True)
        except Listing.DoesNotExist:
            return Response({'error': 'Listing not found'}, status=status.HTTP_404_NOT_FOUND)
        
        like, created = ListingLike.objects.get_or_create(listing=listing, user=request.user)
        if not created:
            return Response({'error': 'Already favorited'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({'success': True, 'message': 'Added to favorites'})


@extend_schema(
    responses={
        200: inline_serializer("FavoritesRemoveResponse", fields={
            "success": serializers.BooleanField(),
            "message": serializers.CharField()
        })
    }
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def favorites_remove(request, favorite_id):
    """Remove a listing from favorites by favorite ID or listing ID."""
    try:
        # Try to find by favorite ID first
        like = ListingLike.objects.filter(id=favorite_id, user=request.user).first()
        if not like:
            # If not found, try to find by listing ID
            like = ListingLike.objects.filter(listing_id=favorite_id, user=request.user).first()
        
        if like:
            like.delete()
            return Response({'success': True, 'message': 'Removed from favorites'})
        else:
            return Response({'error': 'Favorite not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
