from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from accounts.serializers import UserSerializer
from listings.serializers import ListingMediaSerializer
from marketplace.models import (
    MarketplaceItem,
    ProductAttributeValue,
    SellerPaymentMethod,
    SellerProfile,
    Store,
    StoreFollow,
)
from marketplace.constants import StoreCategory
from marketplace.publish_guards import enforce_marketplace_publish_rules, is_transitioning_to_published
from marketplace.services.marketplace_service import save_product_attribute_values
from marketplace.services.store_service import sync_store_from_seller_profile


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    attribute_key = serializers.CharField(source='attribute.key', read_only=True)
    value = serializers.SerializerMethodField()

    class Meta:
        model = ProductAttributeValue
        fields = ['id', 'attribute', 'attribute_name', 'attribute_key', 'value']

    @extend_schema_field(serializers.CharField())
    def get_value(self, obj):
        return obj.get_value()


class MarketplaceItemSerializer(serializers.ModelSerializer):
    media = ListingMediaSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    categoryName = serializers.CharField(source='category.name', read_only=True)
    owner_name = serializers.SerializerMethodField()
    ownerName = serializers.CharField(source='owner.username', read_only=True)
    isPublished = serializers.BooleanField(source='is_published', read_only=True)
    isVerified = serializers.BooleanField(source='is_verified', read_only=True)
    viewCount = serializers.IntegerField(source='view_count', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    is_ghost_listing = serializers.SerializerMethodField()
    isGhostListing = serializers.SerializerMethodField()
    seller_status_message = serializers.SerializerMethodField()
    similar_listings = serializers.SerializerMethodField()

    class Meta:
        model = MarketplaceItem
        fields = [
            'id', 'category', 'category_name', 'categoryName', 'owner', 'owner_name', 'ownerName',
            'title', 'description', 'price', 'status', 'listing_type', 'store',
            'condition', 'city', 'address', 'latitude', 'longitude',
            'specs', 'attribute_values', 'is_published', 'isPublished', 'view_count', 'viewCount', 
            'created_at', 'createdAt', 'updated_at', 'updatedAt', 'media', 
            'stock_quantity', 'track_inventory', 'low_stock_threshold', 'allow_backorders',
            'delivery_is_free', 'delivery_fee',
            'is_verified', 'isVerified', 'is_flagged', 'is_ghost_listing', 'isGhostListing', 
            'seller_status_message', 'similar_listings'
        ]
        read_only_fields = ['owner', 'view_count', 'created_at', 'updated_at']

    def validate(self, data):
        """Ensure the seller has an active store before listing."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
             return data

        # Check if user has a seller profile
        if not hasattr(request.user, 'seller_profile'):
             raise serializers.ValidationError({"non_field_errors": "You must have a seller profile to list items."})
        
        # Check for active stores
        active_stores = request.user.seller_profile.stores.filter(is_active=True)
        if not active_stores.exists():
            raise serializers.ValidationError({"non_field_errors": "You must create an active store before you can list items."})
        
        # If store is provided, verify it belongs to the user
        store = data.get('store')
        if store:
            if store.seller.user != request.user:
                raise serializers.ValidationError({"store": "This store does not belong to you."})
            if not store.is_active:
                raise serializers.ValidationError({"store": "Selected store is not active."})
        else:
            # Automatically assign the store if they only have one
            if active_stores.count() == 1:
                data['store'] = active_stores.first()
            else:
                raise serializers.ValidationError({"store": "Please select a store for your listing."})

        inst = getattr(self, 'instance', None)
        transitioning = is_transitioning_to_published(inst, data)
        enforce_marketplace_publish_rules(
            user=request.user,
            transitioning_to_published=transitioning,
        )

        return data

    @extend_schema_field(serializers.BooleanField())
    def get_is_ghost_listing(self, obj):
        return obj.is_ghost_listing

    @extend_schema_field(serializers.BooleanField())
    def get_isGhostListing(self, obj):
        return obj.is_ghost_listing

    @extend_schema_field(serializers.CharField())
    def get_owner_name(self, obj):
        if obj.owner:
            return obj.owner.username
        return "Deleted Seller"

    def create(self, validated_data):
        specs = validated_data.get('specs', {})
        item = super().create(validated_data)
        save_product_attribute_values(item, specs)
        return item

    def update(self, instance, validated_data):
        specs = validated_data.get('specs', {})
        item = super().update(instance, validated_data)
        if 'specs' in validated_data:
            save_product_attribute_values(item, specs)
        return item

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_seller_status_message(self, obj):
        if obj.is_ghost_listing:
            return "This seller is banned or removed. Find similar products below."
        return None

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_similar_listings(self, obj):
        from listings.models import ListingMedia

        similar = list(obj.get_similar_listings(limit=6))
        if not similar:
            return []
        request = self.context.get('request')
        ids = [s.id for s in similar]
        first_media = {}
        for m in (
            ListingMedia.objects.filter(listing_id__in=ids).order_by('listing_id', 'order', 'id')
        ):
            if m.listing_id not in first_media:
                first_media[m.listing_id] = m

        result = []
        for s in similar:
            media_url = None
            media = first_media.get(s.id)
            if media and media.file:
                if request:
                    media_url = request.build_absolute_uri(media.file.url)
                else:
                    media_url = media.file.url
            result.append({
                'id': s.id,
                'title': s.title,
                'price': float(s.price) if s.price and not s.is_ghost_listing else None,
                'currency': s.currency,
                'city': s.city,
                'status': s.status,
                'thumbnail': media_url,
                'category_name': s.category.name if s.category else None,
            })
        return result

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.is_ghost_listing:
            data.pop('price', None)
        return data


class SellerPaymentMethodSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source='get_provider_display', read_only=True)
    # Allow writing account_number, but it will be masked in the representation
    account_number = serializers.CharField(write_only=True)
    masked_account_number = serializers.CharField(read_only=True)

    class Meta:
        model = SellerPaymentMethod
        fields = [
            'id', 'provider', 'provider_name', 'account_name', 
            'account_number', 'masked_account_number', 'is_active'
        ]
        read_only_fields = ['id']

    def to_representation(self, instance):
        """Override to provide masked_account_number as account_number for legacy frontend support if needed."""
        data = super().to_representation(instance)
        # For security, we never return the raw account_number in the representation
        # We can also populate 'account_number' with the masked version for the frontend
        data['account_number'] = instance.masked_account_number
        return data


def _normalized_verification_status(obj: SellerProfile) -> str:
    vs = (getattr(obj, 'verification_status', None) or '').strip()
    if vs in ('incomplete', 'pending_id'):
        return 'pending'
    if vs:
        return vs
    if obj.is_verified:
        return 'verified'
    if obj.verification_documents:
        return 'pending'
    return 'not_submitted'


class SellerProfilePublicSerializer(serializers.ModelSerializer):
    """Safe subset for non-owners (no tax IDs, documents, or payout internals)."""

    username = serializers.CharField(source='user.username', read_only=True)
    verification_status = serializers.SerializerMethodField()

    class Meta:
        model = SellerProfile
        fields = [
            'id',
            'username',
            'business_name',
            'store_name',
            'store_location',
            'store_logo',
            'store_description',
            'is_verified',
            'average_rating',
            'total_reviews',
            'verification_status',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'username',
            'business_name',
            'store_name',
            'store_location',
            'store_logo',
            'store_description',
            'is_verified',
            'average_rating',
            'total_reviews',
            'verification_status',
            'created_at',
        ]

    @extend_schema_field(serializers.CharField())
    def get_verification_status(self, obj):
        return _normalized_verification_status(obj)


class SellerProfileOwnerSerializer(serializers.ModelSerializer):
    """Full seller profile for the owning user and staff."""

    user = UserSerializer(read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    verification_status = serializers.SerializerMethodField()
    payment_methods = SellerPaymentMethodSerializer(many=True, read_only=True)
    store_categories = serializers.ListField(
        child=serializers.ChoiceField(choices=StoreCategory.choices),
        required=False,
        allow_empty=False,
    )

    def validate(self, data):
        cats = data.get('store_categories')
        if cats is not None:
            seen = []
            for x in cats:
                if x not in seen:
                    seen.append(x)
            data['store_categories'] = seen
            if 'other' in seen:
                if 'store_category_other' in data:
                    data['store_category_other'] = (data.get('store_category_other') or '').strip()
                other_text = (data.get('store_category_other') or '').strip() or (
                    (getattr(self.instance, 'store_category_other', None) or '').strip()
                )
                if not other_text:
                    raise serializers.ValidationError(
                        {'store_category_other': 'Describe what you sell when Other is selected.'}
                    )
        return data

    def validate_store_name(self, value):
        if value is None:
            return value
        v = (value or '').strip()
        if not v:
            return ''
        instance = getattr(self, 'instance', None)
        qs = SellerProfile.objects.filter(store_name__iexact=v)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError('This store name is already taken.')
        return v[:100]

    def update(self, instance, validated_data):
        if (
            'business_name' not in validated_data
            and 'store_name' in validated_data
            and (validated_data.get('store_name') or '').strip()
        ):
            validated_data['business_name'] = validated_data['store_name'][:200]
        inst = super().update(instance, validated_data)
        sync_store_from_seller_profile(inst)
        return inst

    class Meta:
        model = SellerProfile
        fields = [
            'id',
            'user',
            'user_id',
            'username',
            'business_name',
            'business_type',
            'tax_id',
            'business_phone',
            'business_email',
            'business_address',
            'store_name',
            'store_category',
            'store_categories',
            'store_category_other',
            'store_location',
            'store_logo',
            'store_description',
            'notification_orders',
            'notification_messages',
            'notification_reviews',
            'notification_marketing',
            'auto_accept_orders',
            'require_phone_confirmation',
            'shipping_method',
            'return_policy',
            'is_verified',
            'verified_at',
            'verification_documents',
            'verification_status',
            'payment_methods',
            'average_rating',
            'total_reviews',
            'total_sales',
            'is_active',
            'suspended_at',
            'suspension_reason',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'user',
            'is_verified',
            'is_active',
            'verified_at',
            'verification_status',
            'average_rating',
            'total_reviews',
            'total_sales',
            'created_at',
            'updated_at',
        ]

    @extend_schema_field(serializers.CharField())
    def get_verification_status(self, obj):
        return _normalized_verification_status(obj)


class SellerProfileSerializer(SellerProfileOwnerSerializer):
    """Read: public projection for strangers; write: full owner payload."""

    def to_representation(self, instance):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            if instance.user_id == user.id or user.is_staff:
                return super().to_representation(instance)
        return SellerProfilePublicSerializer(instance, context=self.context).to_representation(instance)


class StoreSerializer(serializers.ModelSerializer):
    seller = SellerProfilePublicSerializer(read_only=True)
    seller_id = serializers.IntegerField(source='seller.id', read_only=True)
    seller_name = serializers.SerializerMethodField()
    is_followed = serializers.SerializerMethodField()
    follower_count = serializers.IntegerField(source='total_followers', read_only=True)

    class Meta:
        model = Store
        fields = [
            'id',
            'seller',
            'seller_id',
            'seller_name',
            'name',
            'slug',
            'description',
            'logo',
            'banner',
            'is_active',
            'is_featured',
            'contact_email',
            'contact_phone',
            'website',
            'social_links',
            'total_listings',
            'total_sales',
            'total_followers',
            'is_followed',
            'follower_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'slug',
            'total_listings',
            'total_sales',
            'total_followers',
            'created_at',
            'updated_at',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            if getattr(instance.seller, 'user_id', None) == user.id or getattr(user, 'is_staff', False):
                data['seller'] = SellerProfileOwnerSerializer(instance.seller, context=self.context).data
        return data

    @extend_schema_field(serializers.CharField())
    def get_seller_name(self, obj):
        if obj.seller and obj.seller.user:
            return obj.seller.user.username
        return 'Deleted Store'

    @extend_schema_field(serializers.BooleanField())
    def get_is_followed(self, obj):
        ann = getattr(obj, 'is_followed', None)
        if ann is not None:
            return bool(ann)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return StoreFollow.objects.filter(user=request.user, store=obj).exists()
        return False


class StoreFollowSerializer(serializers.ModelSerializer):
    """Serializer for store follows."""
    store = StoreSerializer(read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = StoreFollow
        fields = ['id', 'store', 'user', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']
