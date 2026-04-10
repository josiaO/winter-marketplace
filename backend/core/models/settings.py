from django.db import models
from .base import BaseModel

class SiteConfiguration(BaseModel):
    """
    Singleton-like model for global site settings.
    Only one active configuration should exist.
    """
    support_phone = models.CharField(max_length=20, blank=True, null=True)
    support_email = models.EmailField(blank=True, null=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # Visual Branding
    logo = models.ImageField(upload_to='site/logo/', blank=True, null=True)
    banner = models.ImageField(upload_to='site/banner/', blank=True, null=True)
    
    # Direct Admin Contact Info for "inputting the admin contact"
    admin_contact_name = models.CharField(max_length=100, blank=True, null=True)
    admin_contact_phone = models.CharField(max_length=20, blank=True, null=True)
    admin_contact_whatsapp = models.CharField(max_length=20, blank=True, null=True)

    # Platform Settings
    platform_name = models.CharField(max_length=100, default="SmartDalali")
    platform_fee = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    min_listing_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    max_listing_price = models.DecimalField(max_digits=12, decimal_places=2, default=100000000.00)
    
    # Feature Toggles
    enable_escrow = models.BooleanField(default=True)
    auto_approve_listings = models.BooleanField(default=False)
    
    # Verification Requirements
    require_phone_verification = models.BooleanField(default=True)
    require_email_verification = models.BooleanField(default=True)
    
    # Notification Settings
    enable_push_notifications = models.BooleanField(default=True)
    enable_email_notifications = models.BooleanField(default=True)
    
    # Regional Settings
    default_currency = models.CharField(max_length=10, default="TZS")
    default_language = models.CharField(max_length=10, default="en")

    class Meta:
        verbose_name = "Site Configuration"
        verbose_name_plural = "Site Configuration"

    def __str__(self):
        return "Global Site Configuration"

    def save(self, *args, **kwargs):
        if self.is_active:
            # Ensure only one configuration is active
            SiteConfiguration.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        """Return the active singleton row, or create one. Collapse duplicate actives if any."""
        active = list(cls.objects.filter(is_active=True).order_by("id"))
        if len(active) > 1:
            keeper = active[0]
            cls.objects.filter(is_active=True).exclude(pk=keeper.pk).update(is_active=False)
            return keeper
        if len(active) == 1:
            return active[0]
        return cls.objects.create(is_active=True)
