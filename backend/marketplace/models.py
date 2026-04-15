from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from core.models.base import BaseModel
from core.encryption import get_encryptor
from listings.models import Listing
from marketplace.constants import StoreCategory, VerificationStatus

# --- Listing vs MarketplaceItem -------------------------------------------------
# `MarketplaceItem` subclasses `Listing` (Django multi-table inheritance). One product
# has one `listings_listing` row; marketplace-only rules (e.g. leaf category) live on
# `marketplace_marketplaceitem`. Stock and pricing are NOT duplicated — they are read
# and written on the parent `Listing` / `BaseListing` fields.


class MarketplaceItem(Listing):
    """Marketplace-facing listing: same DB listing row + extra validation (e.g. leaf category)."""
    class Meta:
        verbose_name = _("Marketplace Item")
        verbose_name_plural = _("Marketplace Items")
        ordering = ['-created_at']
        app_label = 'marketplace'
        # Explicitly exclude indexes - they're defined on the parent Listing model
        # In multi-table inheritance, indexes on parent fields cannot be on child model
        indexes = []

    def __str__(self):
        return f"[{self.category.name if self.category else 'No Category'}] {self.title}"

    def clean(self):
        """Enforce listing only in leaf categories."""
        if self.category and not self.category.is_leaf():
            raise ValidationError(
                _("Sellers can only list in leaf categories. '%(category)s' is a parent category.") % {
                    'category': self.category.name
                }
            )
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class SellerProfile(BaseModel):
    """
    Seller profile for marketplace sellers.
    Extends user account with seller-specific information.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Capture current values for 'save()' signals without triggering DB lookups for deferred fields.
        # Direct access to self.field triggers refresh_from_db if deferred, leading to recursion.
        self._presale_verification_status = self.__dict__.get('verification_status')
        self._presale_total_sales = self.__dict__.get('total_sales')
        self._presale_completed_orders = self.__dict__.get('completed_orders')

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_profile',
        help_text="User account associated with this seller profile"
    )
    
    # Business Information
    business_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Business/Store name"
    )
    business_type = models.CharField(
        max_length=50,
        choices=(
            ('individual', _('Individual Seller')),
            ('business', _('Business')),
            ('retailer', _('Retailer')),
            ('wholesaler', _('Wholesaler')),
        ),
        default='individual'
    )
    tax_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Tax identification number"
    )
    
    # Contact Information
    business_phone = models.CharField(max_length=20, blank=True)
    business_email = models.EmailField(blank=True)
    business_address = models.TextField(blank=True)
    
    # Verification
    is_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Verified seller badge"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_documents = models.JSONField(
        default=list,
        blank=True,
        help_text="List of uploaded verification document URLs"
    )
    
    store_name = models.CharField(max_length=100, blank=True, db_index=True)
    store_categories = models.JSONField(
        default=list,
        blank=True,
        help_text=_('What the seller sells; list of category slugs (e.g. electronics, fashion).'),
    )
    store_category_other = models.CharField(
        max_length=200,
        blank=True,
        help_text=_('Details when "other" is selected among store categories.'),
    )
    store_category = models.CharField(
        max_length=50,
        choices=StoreCategory.choices,
        blank=True,
        help_text=_('Legacy primary category; kept in sync with the first entry in store_categories.'),
    )
    store_location = models.CharField(max_length=100, blank=True)
    seller_type = models.CharField(
        max_length=20,
        choices=(
            ('product', _('Physical / Digital Product')),
            ('service', _('Service')),
        ),
        default='product',
        db_index=True,
        help_text=_('Whether the seller offers products or services.'),
    )
    store_logo = models.ImageField(
        upload_to='store_logos/',
        blank=True,
        null=True,
    )
    store_banner = models.ImageField(
        upload_to='store_banners/',
        blank=True,
        null=True,
        help_text=_("Banner image for the seller's storefront")
    )
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.INCOMPLETE,
        db_index=True,
    )
    products_limit = models.PositiveIntegerField(default=50)
    payout_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=500000.00,
        help_text=_('Monthly payout cap in TZS; 0 means unlimited after business upgrade'),
    )
    total_sales = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0.00,
        help_text=_('Total sales revenue in TZS (denormalized)'),
    )
    completed_orders = models.PositiveIntegerField(
        default=0,
        help_text=_('Count of completed orders (denormalized)'),
    )
    is_business_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_('Verified Business badge after optional business upgrade'),
    )

    # Ratings Summary (denormalized for performance)
    average_rating = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)],
        help_text="Average rating from reviews"
    )
    total_reviews = models.PositiveIntegerField(default=0)
    
    # Status
    is_active = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Store visible to buyers when True and identity verified"
    )
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)

    # Seller Settings
    store_description = models.TextField(blank=True)
    notification_orders = models.BooleanField(default=True)
    notification_messages = models.BooleanField(default=True)
    notification_reviews = models.BooleanField(default=True)
    notification_marketing = models.BooleanField(default=False)
    
    auto_accept_orders = models.BooleanField(default=False)
    require_phone_confirmation = models.BooleanField(default=True)
    
    shipping_method = models.CharField(
        max_length=50,
        default='standard',
        choices=(
            ('standard', _('Standard Shipping')),
            ('express', _('Express Shipping')),
            ('pickup', _('Local Pickup')),
        )
    )
    return_policy = models.TextField(
        default='7 days return policy for defective items',
        blank=True
    )
    
    class Meta:
        verbose_name = _("Seller Profile")
        verbose_name_plural = _("Seller Profiles")
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['store_name'],
                condition=models.Q(store_name__gt=''),
                name='uniq_sellerprofile_store_name_when_set',
            ),
        ]
        indexes = [
            models.Index(fields=['is_verified', 'is_active']),
            models.Index(fields=['verification_status', 'is_active']),
            models.Index(fields=['average_rating', '-completed_orders']),
        ]
    
    def __str__(self):
        return f"Seller: {self.user.username} ({self.business_name or 'Individual'})"

    def save(self, *args, **kwargs):
        # Denormalize legacy single category for filters / old clients.
        valid = {c[0] for c in StoreCategory.choices}
        if self.store_categories:
            cleaned = [str(x) for x in self.store_categories if str(x) in valid]
            self.store_categories = cleaned
            if cleaned:
                self.store_category = cleaned[0]
            elif self.store_category not in valid:
                self.store_category = ''
        elif self.store_category in valid:
            self.store_categories = [self.store_category]
        from marketplace.services.seller_service import SellerService

        SellerService.sync_verification_derivatives(self)
        uf = kwargs.get('update_fields')
        if uf is not None:
            kwargs['update_fields'] = list(set(uf) | {'is_verified', 'is_active'})
        super().save(*args, **kwargs)
    
    def update_ratings(self):
        """Recalculate average rating using the Marketplace service."""
        from marketplace.services.seller_service import SellerService

        return SellerService.update_seller_ratings(self)


class Store(BaseModel):
    """
    Storefront for sellers.
    A seller can have multiple stores (e.g., different brands or categories).
    """
    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name='stores',
        help_text="Seller who owns this store"
    )
    
    # Store Information
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(
        upload_to='stores/logos/',
        blank=True,
        null=True
    )
    banner = models.ImageField(
        upload_to='stores/banners/',
        blank=True,
        null=True
    )
    
    # Store Settings
    is_active = models.BooleanField(
        default=True,
        db_index=True
    )
    is_featured = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Featured stores appear in marketplace highlights"
    )
    
    # Contact
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    
    # Social Media
    social_links = models.JSONField(
        default=dict,
        blank=True,
        help_text="Social media links (facebook, instagram, twitter, etc.)"
    )
    
    # Statistics (denormalized)
    total_listings = models.PositiveIntegerField(default=0)
    total_sales = models.PositiveIntegerField(default=0)
    total_followers = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = _("Store")
        verbose_name_plural = _("Stores")
        ordering = ['-is_featured', '-total_sales', 'name']
        indexes = [
            models.Index(fields=['seller', 'is_active']),
            models.Index(fields=['is_featured', '-total_sales']),
        ]
    
    def __str__(self):
        return f"{self.name} (by {self.seller.user.username})"
    
    def update_statistics(self):
        """Recalculate store statistics and save to DB."""
        from marketplace.services.store_service import update_store_statistics

        return update_store_statistics(self)


class StoreFollow(BaseModel):
    """Users following a store."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='followed_stores'
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='followers'
    )
    
    class Meta:
        unique_together = ('user', 'store')
        verbose_name = _("Store Follow")
        verbose_name_plural = _("Store Follows")
    
    def __str__(self):
        return f"{self.user.username} follows {self.store.name}"


class ProductAttributeValue(BaseModel):
    """Normalized storage for dynamic attribute values."""
    product = models.ForeignKey(
        MarketplaceItem,
        related_name="attribute_values",
        on_delete=models.CASCADE
    )
    attribute = models.ForeignKey(
        'catalog.Attribute',
        on_delete=models.CASCADE,
        related_name='product_values'
    )
    
    value_text = models.CharField(max_length=255, null=True, blank=True)
    value_number = models.FloatField(null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)
    value_option = models.ForeignKey(
        'catalog.AttributeOption',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='product_values'
    )

    class Meta:
        unique_together = ('product', 'attribute')
        verbose_name = _("Product Attribute Value")
        verbose_name_plural = _("Product Attribute Values")

    def __str__(self):
        return f"{self.product.title} - {self.attribute.name}: {self.get_value()}"

    def get_value(self):
        """Helper to get the actual value regardless of type."""
        if self.attribute.field_type == 'select':
            return self.value_option.value if self.value_option else None
        elif self.attribute.field_type == 'number':
            return self.value_number
        elif self.attribute.field_type == 'boolean':
            return self.value_boolean
        return self.value_text


class ProductModerationLog(BaseModel):
    """Audit trail for automated image moderation checks."""

    product = models.ForeignKey(
        MarketplaceItem,
        on_delete=models.CASCADE,
        related_name="moderation_logs",
    )
    image_url = models.URLField(max_length=1000, blank=True)
    is_safe = models.BooleanField(default=True, db_index=True)
    unsafe_reasons = models.JSONField(default=list, blank=True)
    safe_search_result = models.JSONField(default=dict, blank=True)
    moderated_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _("Product Moderation Log")
        verbose_name_plural = _("Product Moderation Logs")
        ordering = ["-moderated_at"]

    def __str__(self):
        return f"Moderation for product #{self.product_id} ({'safe' if self.is_safe else 'unsafe'})"


class SellerPaymentMethod(BaseModel):
    """
    Model for storing seller payment methods (M-PESA, TIGO-PESA, etc.).
    """
    PAYMENT_PROVIDERS = (
        # ── Mobile Money ───────────────────────────────────────────────────
        ('mpesa',          'M-PESA (Vodacom)'),
        ('tigo_pesa',      'Tigo Pesa'),
        ('airtel_money',   'Airtel Money'),
        ('halopesa',       'HaloPesa'),
        ('ezypesa',        'EzyPesa'),
        ('azampesa',       'AzamPesa'),
        # ── Banks (via Selcom) ──────────────────────────────────────────
        ('bank',           'Bank Transfer'),
        # ── Cards ────────────────────────────────────────────────────────────────
        ('card_visa',       'Visa'),
        ('card_mastercard',  'Mastercard'),
        ('card_unionpay',    'UnionPay'),
        # ── Selcom Till / TanQR ───────────────────────────────────────────
        ('till',            'Selcom Till / TanQR'),
    )

    seller = models.ForeignKey(SellerProfile, related_name='payment_methods', on_delete=models.CASCADE)
    provider = models.CharField(max_length=50, choices=PAYMENT_PROVIDERS)
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Seller Payment Method"
        verbose_name_plural = "Seller Payment Methods"
        ordering = ['provider']

    def __str__(self):
        return f"{self.seller.business_name} - {self.get_provider_display()} ({self.masked_account_number})"

    def save(self, *args, **kwargs):
        # Encrypt account_number if it's not already encrypted (naive check: Fernet starts with 'gAAAAA')
        # Standard Fernet tokens are Base64 encoded and start with 'gAAAAA'
        if self.account_number and not self.account_number.startswith('Z0FBQUFB'): # Base64 for 'gAAAAA'
             encryptor = get_encryptor()
             self.account_number = encryptor.encrypt(self.account_number)
        super().save(*args, **kwargs)

    @property
    def decrypted_account_number(self):
        if not self.account_number:
            return ""
        encryptor = get_encryptor()
        return encryptor.decrypt(self.account_number)

    @property
    def masked_account_number(self):
        raw = self.decrypted_account_number
        if not raw:
            return "****"
        if len(raw) <= 4:
            return raw
        return "****" + raw[-4:]

