"""
escrow_engine.providers.base
-----------------------------
Abstract interface every payment provider must implement.

External developers interact ONLY with the engine's service layer.
They NEVER touch provider classes directly.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from escrow_engine.models import Transaction


@dataclass
class PaymentResult:
    """Standardised result returned by every provider method."""
    success: bool
    payment_url: str = ''        # redirect URL (checkout flows)
    gateway_reference: str = ''  # provider-side transaction ID
    raw_payload: dict = None     # verbatim gateway response
    error: str = ''              # human-readable failure reason

    def __post_init__(self):
        if self.raw_payload is None:
            self.raw_payload = {}


class BasePaymentProvider(ABC):
    """
    Abstract base for all payment gateway integrations.

    Implementations:
      - SelcomProvider (M-Pesa / Tigo / Airtel via Selcom aggregator)
      - StripeProvider  (future)
      - MpesaProvider   (future — direct Daraja API)
    """

    @abstractmethod
    def initiate_payment(self, transaction: 'Transaction', **kwargs) -> PaymentResult:
        """
        Start a payment request for the given transaction.
        Returns a PaymentResult with payment_url for redirect / STK push.
        """
        ...

    @abstractmethod
    def verify_payment(self, gateway_data: dict) -> PaymentResult:
        """
        Verify a payment notification/callback from the gateway.
        gateway_data is the raw payload from the webhook or polling call.
        Returns PaymentResult indicating success/failure + gateway_reference.
        """
        ...

    def query_payment_status(self, transaction: 'Transaction') -> PaymentResult:
        """
        Server-to-server payment status for a transaction (redirect / polling flows).
        Default: not supported — subclasses (e.g. Selcom) override when an API exists.
        """
        return PaymentResult(
            success=False,
            error='payment_status_query_not_supported',
            gateway_reference='',
            raw_payload={},
        )

    @abstractmethod
    def refund(self, transaction: 'Transaction', amount=None, reason: str = '') -> PaymentResult:
        """
        Initiate a refund for a transaction.
        amount defaults to the full transaction amount if not provided.
        """
        ...

    @abstractmethod
    def disburse(
        self,
        transaction: 'Transaction',
        account_number: str,
        account_name: str,
        bank_code: str,
        *,
        amount: Optional[Decimal] = None,
    ) -> PaymentResult:
        """
        Disburse funds to the seller's mobile wallet or bank account.
        When ``amount`` is set, it must match the persisted Payout amount (post-fees).
        Otherwise falls back to ``transaction.amount``.
        """
        ...
