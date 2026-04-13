from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from utils.generate_code import generate_code
# from cloudinary.models import CloudinaryField  # Replaced with standard ImageField

class Profile(models.Model):
    user = models.OneToOneField(User, related_name='profile', on_delete=models.CASCADE)
    name = models.CharField(max_length=50, blank=True, null=True)
    about = models.CharField(max_length=1000, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.CharField(max_length=100, blank=True, null=True)
    image = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    code = models.CharField(max_length=8, default=generate_code)
    firebase_uid = models.CharField(max_length=255, blank=True, null=True, unique=True)
    email_verified = models.BooleanField(default=False, help_text="Email verified via OTP or Firebase")
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)

    # Notification Preferences
    notification_orders = models.BooleanField(default=True)
    notification_promotions = models.BooleanField(default=False)
    notification_messages = models.BooleanField(default=True)
    # Seller push (FCM): in-app copy + device notification language
    seller_notification_language = models.CharField(
        max_length=2,
        choices=[('sw', 'Swahili'), ('en', 'English')],
        default='sw',
        help_text='Language for seller marketplace push notifications.',
    )

    def __str__(self):
        return self.user.username


# Create or update Profile when User is created or saved
@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    # If the User is updated, ensure the Profile is also saved
    instance.profile.save()

# post_save.connect(create_or_update_profile, sender=User)


class UserAddress(models.Model):
    """
    Model for storing multiple user addresses (shipping, billing, etc.).
    """
    ADDRESS_TYPES = (
        ('shipping', 'Shipping'),
        ('billing', 'Billing'),
        ('home', 'Home'),
        ('office', 'Office'),
    )

    user = models.ForeignKey(User, related_name='addresses', on_delete=models.CASCADE)
    label = models.CharField(max_length=50, choices=ADDRESS_TYPES, default='shipping')
    address_line = models.TextField()
    city = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Address"
        verbose_name_plural = "User Addresses"
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.label} ({self.city})"

    def save(self, *args, **kwargs):
        if self.is_default:
            # Ensure only one address is default for this user
            UserAddress.objects.filter(user=self.user).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class OTP(models.Model):
    """
    One-Time Password model — used for email verification, password reset, and action confirmation.
    """
    PURPOSE_CHOICES = [
        ('verify_email', 'Email Verification'),
        ('password_reset', 'Password Reset'),
        ('confirm_action', 'Action Confirmation'),
        ('delete_account', 'Account Deletion'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=10)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='verify_email')
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'

    def __str__(self):
        return f"OTP({self.user.email}, {self.purpose}, used={self.is_used})"