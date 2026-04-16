"""
escrow_engine.models
--------------------
Central models for the universal escrow / payment engine.

Model hierarchy:
  Transaction         — the single source of truth for any financial event
  TransactionLog      — immutable audit trail
  Payout              — seller disbursement record
  Dispute             — formal dispute against a Transaction
  DisputeEvidence     — files submitted to support a Dispute
  PaymentRecord       — raw gateway interaction log (replaces legacy Transaction)
  PaymentLink         — shareable URL for a Transaction
  PayoutDestination   — decoupled seller payout account record
"""
from .api_key import APIKey, generate_api_secret, hash_api_key, verify_api_key
from .transaction import Transaction, TransactionSource
from .audit import TransactionLog
from .payout import Payout, PayoutDestination
from .dispute import Dispute, DisputeEvidence
from ..state_machine import TransactionStatus, DisputeStatus, DisputeResolution
from .payment_record import PaymentRecord
from .payment_link import PaymentLink
from .gateway_event import GatewayEvent

__all__ = [
    'APIKey',
    'generate_api_secret',
    'hash_api_key',
    'verify_api_key',
    'Transaction',
    'TransactionSource',
    'TransactionLog',
    'Payout',
    'PayoutDestination',
    'Dispute',
    'DisputeStatus',
    'DisputeResolution',
    'DisputeEvidence',
    'PaymentRecord',
    'PaymentLink',
    'GatewayEvent',
]
