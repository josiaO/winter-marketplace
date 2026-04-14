import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from trust.models import UserVerification
from trust.constants import UserVerificationStatus
from marketplace.models import SellerProfile
from marketplace.constants import VerificationStatus
from sellers.models import SellerOnboardingProgress

logger = logging.getLogger(__name__)

@receiver(post_save, sender=UserVerification)
def sync_user_verification_to_seller_profile(sender, instance, **kwargs):
    """
    Sync trust.UserVerification status to marketplace.SellerProfile.
    - Identity verification (id_status) controls the primary seller visibility.
    - Business verification (business_license_status/tin_status) controls the 'Verified Business' upgrade.
    """
    try:
        seller_profile = SellerProfile.objects.get(user=instance.user)
    except SellerProfile.DoesNotExist:
        return

    # 1. Sync Identity Status (Tier 1)
    if instance.id_status == UserVerificationStatus.PENDING:
        seller_profile.verification_status = VerificationStatus.UNDER_REVIEW
    elif instance.id_status == UserVerificationStatus.VERIFIED:
        seller_profile.verification_status = VerificationStatus.VERIFIED
    elif instance.id_status == UserVerificationStatus.REJECTED:
        seller_profile.verification_status = VerificationStatus.REJECTED
    
    # Update identity flags
    seller_profile.is_verified = (instance.id_status == UserVerificationStatus.VERIFIED)
    seller_profile.is_active = seller_profile.is_verified # Auto-activate if verified
    
    # 2. Sync Business Upgrade (Tier 2)
    # A seller is business verified only if both TIN and License are verified (or as per business logic)
    was_business_verified = seller_profile.is_business_verified
    is_now_business_verified = (
        instance.tin_status == UserVerificationStatus.VERIFIED and
        instance.business_license_status == UserVerificationStatus.VERIFIED
    )
    
    seller_profile.is_business_verified = is_now_business_verified
    
    # If newly upgraded, increase limits
    if is_now_business_verified and not was_business_verified:
        seller_profile.products_limit = 0 # Unlimited
        seller_profile.payout_limit = 0 # Unlimited
        logger.info(f"Seller {seller_profile.id} upgraded to Verified Business")

    # 3. Sync Onboarding Progress (for Dashboard)
    onboarding, _ = SellerOnboardingProgress.objects.get_or_create(seller=seller_profile)
    
    # Update identity steps
    if instance.id_status == UserVerificationStatus.VERIFIED:
        onboarding.step_id_approved = True
        onboarding.step_id_submitted = True
    elif instance.id_status == UserVerificationStatus.PENDING:
        onboarding.step_id_submitted = True
    
    # Update business steps
    onboarding.step_business_upgraded = is_now_business_verified
    
    onboarding.save()

    seller_profile.save(update_fields=[
        'verification_status', 
        'is_verified', 
        'is_active', 
        'is_business_verified',
        'products_limit',
        'payout_limit'
    ])
