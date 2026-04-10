import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from .models import Order
from escrow_engine.services.linked_order import linked_order_has_escrow_payment_activity
from commerce.services.inventory import InventoryService
from commerce.services.lifecycle import OrderLifecycleManager

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=60)
def send_order_confirmation_email(self, order_id):
    """Sends a confirmation email to the buyer when an order is placed."""
    try:
        order = Order.objects.get(id=order_id)
        buyer = order.buyer
        subject = f"Order Confirmation - #{order.id}"
        message = f"Hi {buyer.username},\n\nYour order #{order.id} has been placed successfully. Total amount: {order.total_amount} {order.currency}."
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [buyer.email],
            fail_silently=False,
        )
        logger.info(f"Order confirmation email sent for order {order_id}")
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for confirmation email")
    except Exception as exc:
        logger.error(f"Error sending order confirmation email for {order_id}: {exc}")
        raise

@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=60)
def auto_cancel_unpaid_order(self, order_id):
    """Cancels an order if payment is not received within 24 hours."""
    try:
        order = Order.objects.get(id=order_id)
        if order.status == 'pending':
            if not linked_order_has_escrow_payment_activity(order):
                OrderLifecycleManager.cancel_order(
                    order,
                    actor=None,
                    reason='Auto-cancel: unpaid after timeout',
                )
                logger.info(f"Auto-cancelled unpaid order {order_id}")
            else:
                logger.info(
                    "Order %s has linked escrow activity (non-pending checkout), skipping auto-cancel",
                    order_id,
                )
        else:
            logger.info(f"Order {order_id} status is {order.status}, skipping auto-cancel")
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for auto-cancel")
    except Exception as exc:
        logger.error(f"Error in auto_cancel_unpaid_order for {order_id}: {exc}")
        raise

# release_escrow_funds moved to transactions.tasks

# Periodic Tasks for Celery Beat
@shared_task
def check_unpaid_orders_periodic():
    """Periodic task to check and cancel unpaid orders older than 24 hours."""
    cutoff = timezone.now() - timedelta(hours=24)
    unpaid_orders = Order.objects.filter(status='pending', created_at__lte=cutoff)
    count = 0
    for order in unpaid_orders:
        if not linked_order_has_escrow_payment_activity(order):
            auto_cancel_unpaid_order.delay(order.id)
            count += 1
    logger.info(f"Triggered auto-cancel for {count} unpaid orders")

@shared_task
def cleanup_expired_reservations_periodic():
    """Periodic task to release stock from expired cart/order reservations."""
    try:
        count = InventoryService.cleanup_expired_reservations()
        if count > 0:
            logger.info(f"Cleaned up {count} expired stock reservations")
    except Exception as exc:
        logger.error(f"Error in cleanup_expired_reservations_periodic: {exc}")


# Register reconciliation periodic task (actual implementation in tasks_reconciliation).
import commerce.tasks_reconciliation  # noqa: E402, F401
