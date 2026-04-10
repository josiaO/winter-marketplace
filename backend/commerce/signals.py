import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from communications.notification_service import get_notification_service
from .models import Order

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Order)
def fetch_previous_status(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Order.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=Order)
def handle_order_status_notifications(sender, instance, created, **kwargs):
    """
    Send push notifications when an order undergoes significant status changes
    (e.g., Order Created, Shipped, Arrived, Delivered).
    """
    notification_service = get_notification_service()
    
    if created:
        # Order just created (Pending) - notify seller
        message = f"You have a new order pending from {instance.buyer.username}."
        notification_service.notify_generic(
            user=instance.seller,
            title="New Order Received! 🛒",
            message=message,
            notification_type="order",
            related_object_id=instance.id,
            related_object_type="order",
            send_push=True
        )
    else:
        # Existing order, check for status transitions
        old_status = getattr(instance, '_old_status', None)
        new_status = instance.status
        
        if old_status and old_status != new_status:
            # Notify buyer when order is confirmed/shipped/arrived
            if new_status == 'confirmed':
                notification_service.notify_generic(
                    user=instance.buyer,
                    title="Order Confirmed ✅",
                    message=f"Seller has confirmed your order #{instance.id}. Awaiting shipment.",
                    notification_type="order",
                    related_object_id=instance.id,
                    related_object_type="order",
                    send_push=True
                )
            elif new_status == 'shipped':
                notification_service.notify_generic(
                    user=instance.buyer,
                    title="Order Shipped 🚚",
                    message=f"Your order #{instance.id} has been shipped! It is on its way.",
                    notification_type="order",
                    related_object_id=instance.id,
                    related_object_type="order",
                    send_push=True
                )
            elif new_status == 'arrived':
                notification_service.notify_generic(
                    user=instance.buyer,
                    title="Order Arrived 📍",
                    message=f"Your order #{instance.id} has arrived at the destination. Please confirm receipt.",
                    notification_type="order",
                    related_object_id=instance.id,
                    related_object_type="order",
                    send_push=True
                )
            elif new_status == 'completed':
                 notification_service.notify_generic(
                    user=instance.seller,
                    title="Order Completed ✅",
                    message=f"Order #{instance.id} has been completed! Funds will be released to your account.",
                    notification_type="order",
                    related_object_id=instance.id,
                    related_object_type="order",
                    send_push=True
                )
            elif new_status == 'cancelled':
                # Notify the other party
                target_user = instance.seller if getattr(instance, '_cancelled_by_buyer', True) else instance.buyer
                notification_service.notify_generic(
                    user=target_user,
                    title="Order Cancelled ❌",
                    message=f"Order #{instance.id} has been cancelled.",
                    notification_type="order",
                    related_object_id=instance.id,
                    related_object_type="order",
                    send_push=True
                )
            elif new_status == 'disputed':
                notification_service.notify_generic(
                    user=instance.seller,
                    title="Order Disputed ⚠️",
                    message=f"The buyer has opened a dispute for order #{instance.id}.",
                    notification_type="order",
                    related_object_id=instance.id,
                    related_object_type="order",
                    send_push=True
                )

    # ── WebSocket Dashboard Broadcasts ────────────────────────────────────────
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            update_event = {
                'type': 'order_update',
                'order_id': instance.id,
                'status': instance.status,
                'buyer_id': instance.buyer_id,
                'seller_id': instance.seller_id,
                'timestamp': timezone.now().isoformat()
            }
            # 1. Broadcast to Admin Dashboard
            async_to_sync(channel_layer.group_send)('dashboard_admin', update_event)
            
            # 2. Broadcast to Seller Dashboard
            async_to_sync(channel_layer.group_send)(f'dashboard_seller_{instance.seller.id}', update_event)
            
            # 3. Broadcast to Buyer Dashboard
            async_to_sync(channel_layer.group_send)(f'dashboard_buyer_{instance.buyer.id}', update_event)
    except Exception as e:
        logger.warning(f"Failed to broadcast order update via WebSocket: {e}")
