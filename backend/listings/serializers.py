import json
import logging
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import Listing, ListingMedia, ListingLike, ListingView
from core.serializers.media import MediaSerializer
from catalog.models import Category

logger = logging.getLogger(__name__)

class ListingMediaSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ListingMedia
        fields = ['id', 'file', 'file_url', 'media_type', 'caption', 'order']
    
    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_file_url(self, obj):
        """Return absolute URL for the media file."""
        if not obj.file:
            logger.warning(f"ListingMedia {obj.id} has no file field")
            return None
        try:
            # Get the file URL from the storage backend
            url = obj.file.url
            logger.debug(f"Generated file URL for ListingMedia {obj.id}: {url}")
            
            # If it's already an absolute URL (e.g. Cloudinary/S3), return it
            if url.startswith('http://') or url.startswith('https://'):
                return url
            
            # Build absolute URL using request context
            request = self.context.get('request')
            if request:
                absolute_url = request.build_absolute_uri(url)
                logger.debug(f"Built absolute URL: {absolute_url}")
                return absolute_url
            
            # Fallback: ensure URL starts with /
            if not url.startswith('/'):
                url = f'/{url}'
            logger.debug(f"Using fallback URL: {url}")
            return url
        except Exception as e:
            logger.error(f"Error generating file URL for ListingMedia {obj.id}: {str(e)}", exc_info=True)
            # Try to return the file name as a fallback
            if obj.file and hasattr(obj.file, 'name'):
                return f"/media/{obj.file.name}"
            return None

class ListingSerializer(serializers.ModelSerializer):
    media = ListingMediaSerializer(many=True, read_only=True)
    owner_name = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_vertical = serializers.CharField(source='category.vertical', read_only=True, allow_null=True)
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    seller_verified = serializers.SerializerMethodField()
    owner_profile_image = serializers.SerializerMethodField()
    is_ghost_listing = serializers.SerializerMethodField()
    ownerName = serializers.CharField(source='owner.username', read_only=True)
    categoryName = serializers.CharField(source='category.name', read_only=True)
    likesCount = serializers.IntegerField(source='likes.count', read_only=True)
    sellerVerified = serializers.SerializerMethodField()
    ownerProfileImage = serializers.SerializerMethodField()
    isGhostListing = serializers.SerializerMethodField()
    isVerified = serializers.BooleanField(source='is_verified', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    isFeatured = serializers.BooleanField(source='is_featured', read_only=True)
    trust_verification = serializers.SerializerMethodField()
    trustVerification = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'id', 'owner', 'owner_name', 'ownerName', 'title', 'description', 'price',
            'category', 'category_name', 'categoryName', 'category_vertical', 'status', 'city', 'address', 
            'listing_type', 'condition', 'is_published', 'view_count', 'likes_count', 'likesCount',
            'media', 'seller_verified', 'sellerVerified', 'trust_verification', 'trustVerification',
            'is_verified', 'isVerified',
            'is_featured', 'isFeatured',
            'owner_profile_image', 'ownerProfileImage', 'is_ghost_listing', 'isGhostListing',
            'created_at', 'createdAt', 'updated_at', 'updatedAt',
            'track_inventory', 'stock_quantity', 'low_stock_threshold', 'allow_backorders',
            'delivery_is_free', 'delivery_fee', 'specs',
        ]
    read_only_fields = ['owner', 'view_count', 'created_at', 'updated_at']

    def _validate_delivery_fields(self, attrs):
        """Require a positive delivery fee when delivery is not free."""
        inst = self.instance
        is_free = attrs.get('delivery_is_free')
        if is_free is None:
            is_free = inst.delivery_is_free if inst else True

        fee = attrs.get('delivery_fee', serializers.empty)
        if fee is serializers.empty:
            fee = inst.delivery_fee if inst else None
        if fee == '':
            fee = None

        if is_free:
            attrs['delivery_is_free'] = True
            attrs['delivery_fee'] = None
        else:
            if fee is None:
                raise serializers.ValidationError(
                    {'delivery_fee': 'Set a delivery fee in your listing currency, or choose free delivery.'}
                )
            try:
                fee_dec = fee if isinstance(fee, Decimal) else Decimal(str(fee))
            except (InvalidOperation, TypeError, ValueError):
                raise serializers.ValidationError({'delivery_fee': 'Invalid delivery fee.'})
            if fee_dec < 0:
                raise serializers.ValidationError({'delivery_fee': 'Delivery fee cannot be negative.'})
            attrs['delivery_is_free'] = False
            attrs['delivery_fee'] = fee_dec
        return attrs

    @extend_schema_field(serializers.BooleanField())
    def get_is_ghost_listing(self, obj):
        return obj.is_ghost_listing

    @extend_schema_field(serializers.BooleanField())
    def get_isGhostListing(self, obj):
        return obj.is_ghost_listing

    @extend_schema_field(serializers.BooleanField())
    def get_sellerVerified(self, obj):
        return self.get_seller_verified(obj)

    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_ownerProfileImage(self, obj):
        return self.get_owner_profile_image(obj)

    @extend_schema_field(serializers.CharField())
    def get_owner_name(self, obj):
        """Get owner's username or fallback for ghost listings."""
        if obj.owner:
            return obj.owner.username
        return "Deleted Seller"

    def _owner_trust_block(self, obj):
        """
        Trust app (TrustScore): ID + TIN + business license approved by admin => fully_verified.
        Used for marketplace badges and seller_profile on detail.
        """
        empty = {
            'id_verified': False,
            'tin_verified': False,
            'license_verified': False,
            'fully_verified': False,
            'trust_score': None,
        }
        if not getattr(obj, 'owner_id', None):
            return empty
        try:
            from trust.models import TrustScore
            try:
                ts = obj.owner.trust_score
            except ObjectDoesNotExist:
                ts = TrustScore.objects.filter(user_id=obj.owner_id).first()
            if not ts:
                return empty
            full = bool(ts.id_verified and ts.tin_verified and ts.license_verified)
            return {
                'id_verified': bool(ts.id_verified),
                'tin_verified': bool(ts.tin_verified),
                'license_verified': bool(ts.license_verified),
                'fully_verified': full,
                'trust_score': ts.score,
            }
        except Exception:
            return empty

    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_trust_verification(self, obj):
        return self._owner_trust_block(obj)

    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_trustVerification(self, obj):
        return self._owner_trust_block(obj)
    
    @extend_schema_field(serializers.BooleanField())
    def get_seller_verified(self, obj):
        """
        True if trust verification is complete (all three factors) OR legacy seller_profile.is_verified.
        """
        block = self._owner_trust_block(obj)
        if block['fully_verified']:
            return True
        if not obj.owner:
            return False
        try:
            if hasattr(obj.owner, 'seller_profile'):
                return bool(obj.owner.seller_profile.is_verified)
        except Exception:
            pass
        return False
    
    @extend_schema_field(serializers.URLField(allow_null=True))
    def get_owner_profile_image(self, obj):
        """Get owner's profile image."""
        if not obj.owner:
            return None
        try:
            profile = getattr(obj.owner, 'profile', None)
            if profile and profile.image:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(profile.image.url)
                return profile.image.url
        except Exception:
            pass
        return None
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.is_ghost_listing:
            data.pop('price', None)
        return data

    def to_internal_value(self, data):
        """Handle JSON string for specs when sent via multipart/form-data."""
        if 'specs' in data and isinstance(data['specs'], str):
            try:
                # Convert QueryDict to a mutable dict if needed
                if hasattr(data, 'dict'):
                    data = data.dict()
                data['specs'] = json.loads(data['specs'])
            except (ValueError, TypeError):
                logger.warning(f"Failed to parse specs JSON string: {data['specs']}")
        
        return super().to_internal_value(data)

    def validate(self, data):
        data = self._validate_delivery_fields(data)
        request = self.context.get('request')
        instance = getattr(self, 'instance', None)
        if request and request.user.is_authenticated and instance is not None:
            from marketplace.models import MarketplaceItem
            from marketplace.publish_guards import (
                enforce_marketplace_publish_rules,
                is_transitioning_to_published,
            )

            if MarketplaceItem.objects.filter(pk=instance.pk).exists():
                transitioning = is_transitioning_to_published(instance, data)
                enforce_marketplace_publish_rules(
                    user=request.user,
                    transitioning_to_published=transitioning,
                )
        return data

class ListingDetailSerializer(ListingSerializer):
    parent_category = serializers.SerializerMethodField()
    parent_category_name = serializers.SerializerMethodField()
    listing_verified = serializers.SerializerMethodField()
    seller_profile = serializers.SerializerMethodField()
    seller_status_message = serializers.SerializerMethodField()
    similar_listings = serializers.SerializerMethodField()
    featured_listings = serializers.SerializerMethodField()
    attribute_values = serializers.SerializerMethodField()

    class Meta(ListingSerializer.Meta):
        fields = ListingSerializer.Meta.fields + [
            'parent_category', 'parent_category_name', 'latitude', 'longitude',
            'listing_verified', 'seller_profile', 'seller_status_message',
            'similar_listings', 'featured_listings', 'attribute_values',
        ]

    @extend_schema_field(serializers.BooleanField())
    def get_listing_verified(self, obj):
        try:
            from django.contrib.contenttypes.models import ContentType
            from trust.models import ListingVerification
            content_type = ContentType.objects.get_for_model(obj.__class__)
            verification = ListingVerification.objects.filter(
                listing_id=obj.id,
                content_type=content_type,
                is_verified=True
            ).first()
            return verification is not None
        except Exception:
            pass
        return obj.is_verified if hasattr(obj, 'is_verified') else False

    @extend_schema_field(serializers.DictField(child=serializers.CharField(), allow_null=True))
    def get_seller_profile(self, obj):
        if not obj.owner:
            return None
        try:
            seller_profile = obj.owner.seller_profile
        except Exception:
            return None
        block = self._owner_trust_block(obj)
        return {
            'id': seller_profile.id,
            'business_name': seller_profile.business_name,
            'business_type': getattr(seller_profile, 'business_type', '') or '',
            'is_verified': bool(seller_profile.is_verified),
            'average_rating': float(seller_profile.average_rating) if seller_profile.average_rating else 0.0,
            'total_reviews': seller_profile.total_reviews or 0,
            'total_sales': int(seller_profile.completed_orders or 0),
            'trust_score': block['trust_score'] if block['trust_score'] is not None else 0,
            'id_verified': block['id_verified'],
            'tin_verified': block['tin_verified'],
            'license_verified': block['license_verified'],
            'fully_verified': block['fully_verified'],
        }

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_parent_category(self, obj):
        return obj.category.parent.id if obj.category and obj.category.parent else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_parent_category_name(self, obj):
        return obj.category.parent.name if obj.category and obj.category.parent else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_seller_status_message(self, obj):
        if obj.is_ghost_listing:
            if not obj.owner_id or obj.owner is None:
                return "Seller account deleted."
            elif not obj.owner.is_active:
                return "Seller account deactivated."
        return None

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_attribute_values(self, obj):
        """Marketplace catalog attributes (normalized); empty for plain listings."""
        try:
            from marketplace.models import MarketplaceItem

            mi = (
                MarketplaceItem.objects.filter(pk=obj.pk)
                .prefetch_related(
                    'attribute_values__attribute',
                    'attribute_values__value_option',
                )
                .first()
            )
            if not mi:
                return []
            rows = []
            for pav in mi.attribute_values.all():
                attr = pav.attribute
                label = getattr(attr, 'label', None) or attr.name
                key = getattr(attr, 'key', '') or str(attr.id)
                val = pav.get_value()
                rows.append(
                    {
                        'id': pav.id,
                        'attribute_id': attr.id,
                        'key': key,
                        'label': label,
                        'name': attr.name,
                        'value': val,
                    }
                )
            return rows
        except Exception:
            logger.debug(
                'attribute_values for listing %s failed',
                getattr(obj, 'pk', None),
                exc_info=True,
            )
            return []

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_similar_listings(self, obj):
        similar = obj.get_similar_listings(limit=6)
        return [{
            'id': s.id, 'title': s.title, 'price': float(s.price) if s.price else None,
            'currency': s.currency, 'city': s.city
        } for s in similar]

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_featured_listings(self, obj):
        return [] # Simplified for now

class ListingLikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingLike
        fields = ['id', 'listing', 'user', 'created_at']
        read_only_fields = ['user', 'created_at']
