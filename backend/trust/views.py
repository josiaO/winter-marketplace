from rest_framework import viewsets, permissions, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from rest_framework.exceptions import PermissionDenied

from .models import (
    UserVerification,
    PriceAnomaly,
    ListingVerification,
    Review,
    Report,
    ReviewMedia,
    TrustScore,
)
from .serializers import (
    UserVerificationSerializer, PriceAnomalySerializer, ReportSerializer,
    CreateReportSerializer,
    ReviewSerializer, CreateReviewSerializer, ListingVerificationSerializer,
    TrustScoreSerializer
)
from . import services as trust_svc
from .reporting import evaluate_report_automation
from listings.models import Listing
from marketplace.models import SellerProfile
from .services.stats_service import get_listing_review_stats, get_seller_review_stats, get_most_rated_sellers
from .services.verification_service import verify_listing, unverify_listing


class TrustScoreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing trust scores.
    """
    queryset = TrustScore.objects.all()
    serializer_class = TrustScoreSerializer
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get trust score for the current user."""
        score, created = TrustScore.objects.get_or_create(user=request.user)
        if created:
            score.calculate_score()
            score.save()
        serializer = self.get_serializer(score)
        return Response(serializer.data)

class UserVerificationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for user verification
    """
    queryset = UserVerification.objects.all()
    serializer_class = UserVerificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return UserVerification.objects.all().select_related('user')
        return UserVerification.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """Override create to handle find_or_create logic for the current user."""
        verification, _ = UserVerification.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(verification, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Determine status automatically based on what was uploaded
        if 'national_id_front' in request.data:
            verification.id_status = 'pending'
        if 'tin_certificate' in request.data:
            verification.tin_status = 'pending'
        if 'business_license_document' in request.data:
            verification.business_license_status = 'pending'
            
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def verify_id(self, request, pk=None):
        """Verify identity (admin only)."""
        verification = self.get_object()
        trust_svc.verify_user_document(
            verification, 
            doc_type='id', 
            status=request.data.get('status', 'verified'),
            notes=request.data.get('notes', ''),
            admin_user=request.user
        )
        return Response({'status': f'ID verification set to {verification.id_status}'})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def verify_tin(self, request, pk=None):
        """Verify TIN (admin only)."""
        verification = self.get_object()
        trust_svc.verify_user_document(
            verification, 
            doc_type='tin', 
            status=request.data.get('status', 'verified'),
            notes=request.data.get('notes', ''),
            admin_user=request.user
        )
        return Response({'status': f'TIN verification set to {verification.tin_status}'})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def verify_license(self, request, pk=None):
        """Verify Business License (admin only)."""
        verification = self.get_object()
        trust_svc.verify_user_document(
            verification, 
            doc_type='license', 
            status=request.data.get('status', 'verified'),
            notes=request.data.get('notes', ''),
            admin_user=request.user
        )
        return Response({'status': f'Business License verification set to {verification.business_license_status}'})

    def _update_trust_score(self, user, **kwargs):
        """Helper to update user trust score factors (Deprecated: Use trust_svc)."""
        trust_svc.update_user_trust_score(user, **kwargs)


class PriceAnomalyViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for price anomalies. Admin only.
    """
    queryset = PriceAnomaly.objects.all()
    serializer_class = PriceAnomalySerializer
    permission_classes = [permissions.IsAdminUser]


class ReportViewSet(viewsets.ModelViewSet):
    """
    API endpoint for platform abuse reports (listings, users, reviews, messages).
    Staff see all; users see their own submissions. Auto-suspend uses distinct reporters (see settings).
    """
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateReportSerializer
        return ReportSerializer

    def get_permissions(self):
        if self.action in ('update', 'partial_update', 'destroy'):
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = Report.objects.select_related(
            'reporter', 'reported_user', 'subject_user', 'listing', 'review', 'resolved_by'
        )
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        if self.request.user.is_staff:
            return qs.order_by('-created_at')
        return qs.filter(reporter=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        report = serializer.save()
        evaluate_report_automation(report)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        output = ReportSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser], url_path='dismiss')
    def dismiss(self, request, pk=None):
        report = self.get_object()
        report.status = 'dismissed'
        report.resolved_by = request.user
        report.resolution_notes = (request.data.get('resolution_notes') or '').strip()
        report.resolved_at = timezone.now()
        report.save()
        return Response(ReportSerializer(report, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser], url_path='resolve')
    def mark_resolved(self, request, pk=None):
        report = self.get_object()
        report.status = 'resolved'
        report.resolved_by = request.user
        report.resolution_notes = (request.data.get('resolution_notes') or '').strip()
        report.resolved_at = timezone.now()
        report.save()
        return Response(ReportSerializer(report, context=self.get_serializer_context()).data)


class ReviewViewSet(viewsets.ModelViewSet):
    """
    API endpoint for order-based reviews.
    Reviews are tied to orders and sellers.
    """
    queryset = Review.objects.filter(
        is_approved=True,
        is_hidden=False
    ).select_related('buyer', 'seller', 'listing', 'order')
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateReviewSerializer
        return ReviewSerializer
    
    def partial_update(self, request, *args, **kwargs):
        """Allow sellers to reply to reviews."""
        review = self.get_object()
        user = request.user
        
        # Only the seller can reply to their reviews
        if review.seller != user:
            return Response(
                {'error': 'Only the seller can reply to this review.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Only allow updating seller_reply field
        if 'seller_reply' not in request.data:
            return Response(
                {'error': 'Only seller_reply field can be updated.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        review.seller_reply = request.data.get('seller_reply', '')
        review.save()
        
        serializer = self.get_serializer(review)
        return Response(serializer.data)

    def get_queryset(self):
        user = self.request.user
        
        # Extract query parameters
        listing_id = self.request.query_params.get('listing')
        order_id = self.request.query_params.get('order')
        buyer_id = self.request.query_params.get('buyer')
        seller_id = self.request.query_params.get('seller')
        
        # Base filter for public view: approved and not hidden
        base_filter = Q(is_approved=True, is_hidden=False)
        
        # If authenticated, user can also see their own reviews (even if pending/hidden)
        if user.is_authenticated:
            # If no specific filter is provided, we default to the user's own data
            # to prevent showing the entire marketplace reviews in a dashboard context.
            if not any([listing_id, order_id, buyer_id, seller_id]):
                queryset = Review.objects.filter(Q(buyer=user) | Q(seller=user))
            else:
                # Include user's own reviews in the base filter
                base_filter |= Q(buyer=user) | Q(seller=user)
                queryset = Review.objects.filter(base_filter)
        else:
            # Anonymous users only see public approved reviews
            queryset = Review.objects.filter(base_filter)
            
        queryset = queryset.select_related(
            'buyer', 'seller', 'listing', 'order'
        ).prefetch_related('media')
        
        # Filter by listing if provided
        listing_id = self.request.query_params.get('listing')
        if listing_id:
            queryset = queryset.filter(listing_id=listing_id)
        
        # Filter by order if provided
        order_id = self.request.query_params.get('order')
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        
        # Filter by buyer if provided
        buyer_id = self.request.query_params.get('buyer')
        if buyer_id == 'me' and self.request.user.is_authenticated:
            queryset = queryset.filter(buyer=self.request.user)
        elif buyer_id:
            queryset = queryset.filter(buyer_id=buyer_id)
        
        # Filter by seller if provided
        seller_id = self.request.query_params.get('seller')
        if seller_id == 'me' and self.request.user.is_authenticated:
            queryset = queryset.filter(seller=self.request.user)
        elif seller_id:
            queryset = queryset.filter(seller_id=seller_id)
        
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Create review and update seller rating."""
        review = serializer.save()
        
        # Update seller rating using service
        trust_svc.update_seller_rating(review.seller)
        
        # Handle media uploads if present
        images = self.request.FILES.getlist('media')
        for image in images:
            ReviewMedia.objects.create(
                review=review,
                file=image,
                media_type='image'
            )

    @action(detail=False, methods=['get'])
    def listing_stats(self, request):
        """Get review statistics for a listing"""
        listing_id = request.query_params.get('listing')
        if not listing_id:
            return Response({'error': 'listing parameter required'}, status=400)
        
        stats = get_listing_review_stats(listing_id)
        return Response(stats)

    @action(detail=False, methods=['get'])
    def seller_stats(self, request):
        """Get review statistics for a seller"""
        seller_id = request.query_params.get('seller')
        if not seller_id:
            return Response({'error': 'seller parameter required'}, status=400)
        
        stats = get_seller_review_stats(seller_id)
        return Response(stats)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAdminUser])
    def most_rated_sellers(self, request):
        """Get most rated sellers for admin dashboard"""
        limit = int(request.query_params.get('limit', 20))
        result = get_most_rated_sellers(limit=limit)
        return Response(result)


class ListingVerificationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for listing verification (admin only for verify/unverify).
    """
    queryset = ListingVerification.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter queryset based on permissions."""
        queryset = ListingVerification.objects.select_related('verified_by', 'content_type').all()
        
        # Non-admin users can only see their own listing verifications
        if not self.request.user.is_staff:
            # Get listings owned by user
            user_listings = Listing.objects.filter(owner=self.request.user).values_list('id', flat=True)
            queryset = queryset.filter(listing_id__in=user_listings)
        
        # Filter by listing_id if provided
        listing_id = self.request.query_params.get('listing_id')
        if listing_id:
            queryset = queryset.filter(listing_id=listing_id)
        
        return queryset

    serializer_class = ListingVerificationSerializer

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def verify(self, request, pk=None):
        """Verify a listing (admin only)."""
        verification = verify_listing(pk, request.user)
        serializer = self.get_serializer(verification)
        return Response({
            'message': f'Listing #{verification.listing_id} has been verified',
            'verification': serializer.data
        })

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def unverify(self, request, pk=None):
        """Unverify a listing (admin only)."""
        verification = unverify_listing(pk, request.user)
        serializer = self.get_serializer(verification)
        return Response({
            'message': f'Listing #{verification.listing_id} has been unverified',
            'verification': serializer.data
        })

    def create(self, request, *args, **kwargs):
        """Create verification request."""
        listing_id = request.data.get('listing_id')
        if not listing_id:
            return Response({'error': 'listing_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get content type for Listing model
        try:
            listing = Listing.objects.get(id=listing_id)
            content_type = ContentType.objects.get_for_model(listing.__class__)
        except Listing.DoesNotExist:
            return Response({'error': 'Listing not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if verification already exists
        existing = ListingVerification.objects.filter(
            listing_id=listing_id,
            content_type=content_type
        ).first()
        
        if existing:
            serializer = self.get_serializer(existing)
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        serializer = self.get_serializer(data={
            'listing_id': listing_id,
            'content_type': content_type.id,
            'is_verified': False,
            'notes': request.data.get('notes', '')
        })
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def perform_create(self, serializer):
        """Save the verification instance."""
        serializer.save()
