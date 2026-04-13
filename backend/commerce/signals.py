import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from communications.notification_service import get_notification_service

from commerce.seller_notifications import (
    notify_buyer_payment_confirmed_order,
    notify_seller_dispute,
    notify_seller_funds_released,
    notify_seller_new_order_pending_payment,
    notify_seller_payment_in_escrow,
)
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
    Push + in-app notifications on order lifecycle.

    Marketplace rule: ship only after buyer payment (order moves to confirmed when escrow holds).
    """
    notification_service = get_notification_service()

    if created:
        notify_seller_new_order_pending_payment(instance)
    else:
        old_status = getattr(instance, '_old_status', None)
        new_status = instance.status

        if old_status and old_status != new_status:
            if new_status == 'confirmed':
                notify_buyer_payment_confirmed_order(instance)
                notify_seller_payment_in_escrow(instance)
            elif new_status == 'shipped':
                notification_service.notify_generic(
                    user=instance.buyer,
                    title='Order Shipped 🚚',
                    message=f'Your order #{instance.id} has been shipped! It is on its way.',
                    notification_type='order',
                    related_object_id=instance.id,
                    related_object_type='order',
                    send_push=True,
                )
            elif new_status == 'arrived':
                notification_service.notify_generic(
                    user=instance.buyer,
                    title='Order Arrived 📍',
                    message=(
                        f'Your order #{instance.id} has arrived at the destination. '
                        'Please confirm receipt.'
                    ),
                    notification_type='order',
                    related_object_id=instance.id,
                    related_object_type='order',
                    send_push=True,
                )
            elif new_status == 'completed':
                notify_seller_funds_released(instance)
            elif new_status == 'cancelled':
                target_user = instance.seller if getattr(instance, '_cancelled_by_buyer', True) else instance.buyer
                notification_service.notify_generic(
                    user=target_user,
                    title='Order Cancelled ❌',
                    message=f'Order #{instance.id} has been cancelled.',
                    notification_type='order',
                    related_object_id=instance.id,
                    related_object_type='order',
                    send_push=True,
                )
            elif new_status == 'disputed':
                notify_seller_dispute(instance)

    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            update_event = {
                'type': 'order_update',
                'order_id': instance.id,
                'status': instance.status,
                'buyer_id': instance.buyer_id,
                'seller_id': instance.seller_id,
                'timestamp': timezone.now().isoformat(),
            }
            async_to_sync(channel_layer.group_send)('dashboard_admin', update_event)
            async_to_sync(channel_layer.group_send)(f'dashboard_seller_{instance.seller.id}', update_event)
            async_to_sync(channel_layer.group_send)(f'dashboard_buyer_{instance.buyer.id}', update_event)
    except Exception as e:
        logger.warning('Failed to broadcast order update via WebSocket: %s', e)
