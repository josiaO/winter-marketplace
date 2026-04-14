from django.db import models
from django.conf import settings
from .constants import SellerVerificationStatus
from django.utils.translation import gettext_lazy as _
from marketplace.models import SellerProfile
from core.encryption import get_encryptor





from escrow_engine.constants import SELCOM_CHANNELS

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
        return f'{self.seller_id} {self.account_type} {self.masked_account_number}'

    def save(self, *args, **kwargs):
        # Encrypt account_number if not already encrypted
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
