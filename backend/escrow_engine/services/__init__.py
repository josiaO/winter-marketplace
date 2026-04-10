# escrow_engine/services/__init__.py
"""
escrow_engine.services
-----------------------
Single source of truth for all financial business logic.

All three channels (marketplace, external, API) call these functions.
Views contain NO business logic.
Models contain NO business logic (only validation).
"""
from .transaction import create_transaction, get_transaction
from .payment import (
    initiate_payment,
    confirm_payment,
    handle_webhook,
    verify_payment_with_provider,
    verify_payment_status,
    sync_buyer_contact_for_checkout,
)
from .escrow import hold_funds, release_funds, refund_funds, open_dispute, resolve_dispute
from .payout import create_payout, process_payout

__all__ = [
    # Transaction lifecycle
    'create_transaction',
    'get_transaction',
    # Payment
    'initiate_payment',
    'confirm_payment',
    'handle_webhook',
    'verify_payment_with_provider',
    'verify_payment_status',
    'sync_buyer_contact_for_checkout',
    # Escrow
    'hold_funds',
    'release_funds',
    'refund_funds',
    # Dispute
    'open_dispute',
    'resolve_dispute',
    # Payout
    'create_payout',
    'process_payout',
]
