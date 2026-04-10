"""
escrow_engine.signals
---------------------
Signal handlers for the Escrow Engine.

DEPRECATION NOTE: 
The 'sync_order_to_escrow' signal has been DEPRECATED and removed.
Status synchronization between 'commerce.Order' and 'escrow_engine.Transaction'
 is now handled EXPLICITLY and ATOMICALLY by the 
'commerce.services.lifecycle.OrderLifecycleManager'.

Relying on signals for financial state synchronization proved brittle 
and prone to 'Split-Brain' race conditions.
"""
import logging

logger = logging.getLogger(__name__)

# Note: Add future engine-only internal signals here if needed.
