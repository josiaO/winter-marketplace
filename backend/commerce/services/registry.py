"""
commerce.services.registry
---------------------------
Centralized registry for status mappings and order constants.

ORDER_STATUS_TO_TRANSACTION_MAP is a *convention document* for how order
lifecycle lines up with expected escrow states when both domains are healthy.
It does not assign payment status — only escrow_engine mutates Transaction.status.
"""
from escrow_engine.models import TransactionStatus

# Expected pairing when sync is correct (commerce order flow ↔ engine txn state).
ORDER_STATUS_TO_TRANSACTION_MAP = {
    'pending': TransactionStatus.CREATED,
    'confirmed': TransactionStatus.HOLD,
    'processing': TransactionStatus.HOLD,
    'shipped': TransactionStatus.HOLD,
    'arrived': TransactionStatus.HOLD,
    'delivered': TransactionStatus.HOLD,
    'completed': TransactionStatus.RELEASED,
    'cancelled': TransactionStatus.REFUNDED,
    'disputed': TransactionStatus.DISPUTED,
    'refunded': TransactionStatus.REFUNDED,
}

# Formal mapping: Order.status -> Delivery.status
# Ensures the logistics layer mirrors the core Order state.
ORDER_STATUS_TO_DELIVERY_MAP = {
    'pending': 'pending',
    'confirmed': 'preparing',
    'processing': 'preparing',
    'shipped': 'in_transit',
    'arrived': 'out_for_delivery', # Or stayed in_transit depending on carrier
    'delivered': 'delivered',
    'completed': 'delivered',
    'cancelled': 'returned',
    'disputed': 'pending', # Hold delivery update during dispute
}

def get_transaction_status(order_status: str) -> str:
    """Helper to safely map order status to financial status."""
    return ORDER_STATUS_TO_TRANSACTION_MAP.get(order_status, TransactionStatus.CREATED)

def get_delivery_status(order_status: str) -> str:
    """Helper to safely map order status to logistics status."""
    return ORDER_STATUS_TO_DELIVERY_MAP.get(order_status, 'pending')
