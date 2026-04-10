"""
escrow_engine.services.payment_link_service
-------------------------------------------
Specialized service for Managing shareable PaymentLinks, including 
OTP-based identity verification and link-based transaction creation.
"""
import logging
import random
from django.utils import timezone
from django.conf import settings
from django.shortcuts import get_object_or_404
from escrow_engine.models import Transaction, PaymentLink, TransactionSource
from escrow_engine.services import transaction as txn_svc

logger = logging.getLogger(__name__)

def create_payment_link(
    amount,
    currency='TZS',
    seller_user=None,
    seller_phone='',
    seller_email='',
    description='',
    metadata=None,
    external_reference='',
    expires_hours=48,
    title='',
    payment_method='selcom'
) -> PaymentLink:
    """
    Creates both an underlying Transaction and a shareable PaymentLink.
    This consolidates logic previously split between the view and models.
    """
    # 1. Create the underlying escrow transaction
    txn = txn_svc.create_transaction(
        amount=amount,
        currency=currency,
        source=TransactionSource.EXTERNAL,
        seller_user=seller_user,
        seller_phone=seller_phone,
        seller_email=seller_email,
        payment_method=payment_method,
        description=description,
        metadata=metadata or {},
        external_reference=external_reference,
    )

    # 2. Create the payment link
    expires_at = timezone.now() + timezone.timedelta(hours=expires_hours)
    link = PaymentLink.objects.create(
        transaction=txn,
        created_by=seller_user,
        expires_at=expires_at,
        title=title,
        description=description,
    )

    logger.info("Created PaymentLink %s for Transaction %s", link.token, txn.reference)
    return link

def issue_link_otp(link: PaymentLink) -> str:
    """
    Generate and save a multi-digit OTP for the payment link.
    """
    code = f"{random.randint(100000, 999999)}"
    otp_ttl = getattr(settings, 'PAYMENT_LINK_OTP_MINUTES', 10)
    
    link.otp_code = code
    link.otp_expires_at = timezone.now() + timezone.timedelta(minutes=otp_ttl)
    link.otp_verified = False
    link.save(update_fields=['otp_code', 'otp_expires_at', 'otp_verified', 'updated_at'])
    
    logger.info("Issued OTP for PaymentLink %s", link.token)
    return code

def verify_link_otp(link: PaymentLink, code: str, phone: str) -> bool:
    """
    Verify the submitted OTP for a payment link.
    """
    if not link.otp_code or not link.otp_expires_at:
        return False
    if timezone.now() > link.otp_expires_at:
        return False
    if link.otp_code != code.strip():
        return False

    link.otp_verified = True
    link.buyer_phone_verified = phone
    link.save(update_fields=['otp_verified', 'buyer_phone_verified', 'updated_at'])
    
    logger.info("Verified OTP for PaymentLink %s", link.token)
    return True
