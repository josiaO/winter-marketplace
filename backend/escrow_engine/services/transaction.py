"""
escrow_engine.services.transaction
------------------------------------
Transaction creation and retrieval.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Optional

from django.contrib.auth import get_user_model

from escrow_engine.models import Transaction
from escrow_engine.models.transaction import TransactionSource
from escrow_engine.state_machine import TransactionStatus

logger = logging.getLogger(__name__)
User = get_user_model()


def create_transaction(
    *,
    amount: Decimal,
    currency: str = 'TZS',
    source: str = TransactionSource.MARKETPLACE,
    # Internal parties
    buyer_user=None,
    seller_user=None,
    # External parties (off-platform / WhatsApp)
    buyer_phone: str = '',
    buyer_email: str = '',
    seller_phone: str = '',
    seller_email: str = '',
    # API clients
    external_reference: str = '',
    # Optional context
    description: str = '',
    metadata: dict = None,
    payment_method: str = 'selcom',
    # Optional immediate order link
    linked_order=None,
    created_by_api_key=None,
) -> Transaction:
    """
    Create a new escrow Transaction in CREATED state.

    This is the ONE entry point for all three channels:
      - marketplace: pass buyer_user + seller_user
      - external:    pass buyer_phone / seller_phone
      - api:         pass external_reference

    Returns the saved Transaction instance.
    """
    if amount <= Decimal('0'):
        raise ValueError("Transaction amount must be positive.")

    txn = Transaction.objects.create(
        amount=amount,
        currency=currency,
        source=source,
        buyer_user=buyer_user,
        seller_user=seller_user,
        buyer_phone=buyer_phone or '',
        buyer_email=buyer_email or '',
        seller_phone=seller_phone or '',
        seller_email=seller_email or '',
        external_reference=external_reference or '',
        description=description,
        metadata=metadata or {},
        payment_method=payment_method,
        status=TransactionStatus.CREATED,
        created_by_api_key=created_by_api_key,
    )

    if linked_order is not None:
        txn.link_order(linked_order)

    logger.info(
        "Transaction created: ref=%s source=%s amount=%s %s",
        txn.reference, source, amount, currency,
    )
    return txn


def get_transaction(reference: str) -> Transaction:
    """Fetch a transaction by its human-readable reference. Raises DoesNotExist if not found."""
    return Transaction.objects.select_related(
        'buyer_user', 'seller_user', 'linked_order'
    ).get(reference=reference)
