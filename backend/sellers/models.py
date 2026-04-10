from django.db import models
from django.conf import settings
from .constants import SellerVerificationStatus
from django.utils.translation import gettext_lazy as _
from marketplace.models import SellerProfile


class SellerIDVerification(models.Model):
    ID_TYPE_CHOICES = (
        ('national_id', _('National ID')),
        ('passport', _('Passport')),
        ('voters_card', _("Voter's card")),
        ('driving_license', _('Driving license')),
    )

    seller = models.OneToOneField(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name='id_verification',
    )
    id_type = models.CharField(max_length=30, choices=ID_TYPE_CHOICES)
    id_number = models.CharField(max_length=50)
    id_front_image = models.ImageField(upload_to='verifications/id/')
    selfie_with_id = models.ImageField(upload_to='verifications/selfies/')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='seller_id_reviews',
    )
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _('Seller ID verification')
        verbose_name_plural = _('Seller ID verifications')

    def __str__(self):
        return f'ID verification for seller {self.seller_id}'


from escrow_engine.models.payout import SELCOM_CHANNELS

class SellerPayoutAccount(models.Model):
    ACCOUNT_TYPE_CHOICES = SELCOM_CHANNELS

    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name='payout_accounts',
    )
    account_type = models.CharField(
        max_length=20, 
        choices=ACCOUNT_TYPE_CHOICES,
        default='mpesa'
    )
    account_number = models.CharField(max_length=50)
    account_name = models.CharField(max_length=100)
    bank_code = models.CharField(
        max_length=20, 
        blank=True, 
        help_text=_("Selcom bank code (e.g. CRDB, NMB). Required for bank transfers.")
    )
    is_primary = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.seller_id} {self.account_type} {self.account_number}'


class SellerOnboardingProgress(models.Model):
    seller = models.OneToOneField(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name='onboarding_progress',
    )
    step_registration = models.BooleanField(default=False)
    step_store_setup = models.BooleanField(default=False)
    step_id_submitted = models.BooleanField(default=False)
    step_id_approved = models.BooleanField(default=False)
    step_payout_added = models.BooleanField(default=False)
    step_first_product = models.BooleanField(default=False)
    step_business_upgraded = models.BooleanField(default=False)
    upgrade_prompt_sent = models.BooleanField(default=False)

    class Meta:
        verbose_name = _('Seller onboarding progress')

    def __str__(self):
        return f'Progress seller {self.seller_id}'


class SellerBusinessVerification(models.Model):
    STATUS_CHOICES = SellerVerificationStatus.choices

    seller = models.OneToOneField(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name='business_verification',
    )
    business_name = models.CharField(max_length=200)
    business_registration_no = models.CharField(max_length=100, blank=True)
    tin_number = models.CharField(max_length=50, blank=True)
    business_certificate = models.FileField(
        upload_to='verifications/business/',
        blank=True,
        null=True,
    )
    bank_account_number = models.CharField(max_length=50, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account_name = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=SellerVerificationStatus.choices, default=SellerVerificationStatus.PENDING)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='seller_business_reviews',
    )
    rejection_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = _('Seller business verification')


class SellerActionLog(models.Model):
    ACTION_CHOICES = (
        ('approve', _('Approve')),
        ('reject', _('Reject')),
        ('suspend', _('Suspend')),
        ('reinstate', _('Reinstate')),
        ('business_approve', _('Business approve')),
        ('business_reject', _('Business reject')),
    )

    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name='action_logs',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_actions_performed',
    )
    reason = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
