import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from listings.models import ListingLike
from communications.notification_service import get_notification_service
from .models import Message, SupportRequest
from commerce.models import Order
from trust.models import Review
from .tasks import send_generic_notification_task

User = get_user_model()
logger = logging.getLogger(__name__)

@receiver(post_save, sender=ListingLike)
def notify_property_owner_on_like(sender, instance, created, **kwargs):
    """Notify property owner when a user likes their property/listing"""
    if created:
        try:
            # Check if this is a property (Listing subclass)
            listing = instance.listing
            if not listing:
                return

            notification_service = get_notification_service()
            owner = listing.owner
            liker_name = instance.user.get_full_name() or instance.user.username
            
            send_generic_notification_task.delay(
                user_id=owner.id,
                title="New Like! ❤️",
                message=f"{liker_name} liked your {listing.category.name if listing.category else 'listing'}: {listing.title}",
                notification_type="like",
                related_object_id=listing.id,
                related_object_type="listing"
            )
        except Exception as e:
            logger.error(f"Error sending like notification: {e}")

# Listing views are recorded in listings.ListingView + view_count (see listings.services.increment_views).
# Legacy PropertyViewEvent was never written by marketplace flows; per-view push notifications are disabled
# to avoid spamming sellers on every page load.

@receiver(post_save, sender=Message)
def update_conversation_timestamp(sender, instance, created, **kwargs):
    """Update conversation timestamp when a new message is sent"""
    if created:
        try:
            # Saving the conversation handles auto_now=True for updated_at
            # We use update_fields to be efficient, but we must ensure Django 
            # actually updates the timestamp even if we don't manually set it.
            # actually, standard save() is safest for auto_now
            instance.conversation.save() 
        except Exception as e:
            logger.error(f"Error updating conversation timestamp: {e}")


# ─── ORDER NOTIFICATIONS ────────────────────────────────────────────────────

@receiver(post_save, sender=Order)
def notify_on_order_created(sender, instance, created, **kwargs):
    """Notify buyer and seller when an order is created"""
    if created:
        try:
            notification_service = get_notification_service()
            
            # Validate that buyer and seller are different users
            if not instance.buyer:
                logger.error(f"Order {instance.id} has no buyer set")
                return
            
            if not instance.seller:
                logger.error(f"Order {instance.id} has no seller set")
                return
            
            if instance.buyer.id == instance.seller.id:
                logger.error(f"Order {instance.id} has buyer and seller as the same user (ID: {instance.buyer.id})")
                return
            
            # Log for debugging
            logger.info(f"Sending order notifications for order {instance.id}: buyer={instance.buyer.id} ({instance.buyer.username}), seller={instance.seller.id} ({instance.seller.username})")
            
            # Notify buyer
            try:
                send_generic_notification_task.delay(
                    user_id=instance.buyer.id,
                    title="Order Placed! 🛒",
                    message=f"Your order #{instance.id} has been placed successfully. Total: {instance.total_amount} {instance.currency}",
                    notification_type="order",
                    related_object_id=instance.id,
                    related_object_type="order"
                )
                logger.info(f"Buyer notification sent for order {instance.id} to user {instance.buyer.id}")
            except Exception as e:
                logger.error(f"Error sending buyer notification for order {instance.id}: {e}")
            
            # Notify seller - ensure we're using the seller, not the buyer
            try:
                # Double-check we're using the seller
                seller_user = instance.seller
                if seller_user.id == instance.buyer.id:
                    logger.error(f"CRITICAL: Attempted to send seller notification to buyer for order {instance.id}")
                    return
                
                send_generic_notification_task.delay(
                    user_id=seller_user.id,
                    title="New Order Received! 📦",
                    message=f"You have a new order #{instance.id} from {instance.buyer.get_full_name() or instance.buyer.username}. Total: {instance.total_amount} {instance.currency}",
                    notification_type="order",
                    related_object_id=instance.id,
                    related_object_type="order"
                )
                logger.info(f"Seller notification sent for order {instance.id} to user {seller_user.id}")
            except Exception as e:
                logger.error(f"Error sending seller notification for order {instance.id}: {e}")
        except Exception as e:
            logger.error(f"Error sending order creation notification: {e}", exc_info=True)


# Track previous status to detect changes
_order_status_cache = {}

@receiver(pre_save, sender=Order)
def cache_order_status(sender, instance, **kwargs):
    """Cache the previous status before save"""
    if instance.pk:
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            _order_status_cache[instance.pk] = old_instance.status
        except Order.DoesNotExist:
            pass


@receiver(post_save, sender=Order)
def notify_on_order_status_change(sender, instance, **kwargs):
    """Notify buyer and seller when order status changes"""
    try:
        old_status = _order_status_cache.get(instance.pk)
        if old_status and old_status != instance.status:
            notification_service = get_notification_service()
            
            status_messages = {
                'confirmed': "Your order has been confirmed by the seller",
                'processing': "Your order is being processed",
                'shipped': "Your order has been shipped",
                'arrived': "Your order has arrived",
                'delivered': "Your order has been delivered",
                'completed': "Your order has been completed",
                'cancelled': "Your order has been cancelled",
                'disputed': "Your order is under dispute",
            }
            
            message = status_messages.get(instance.status, f"Order status changed to {instance.status}")
            
            # Notify buyer
            send_generic_notification_task.delay(
                user_id=instance.buyer.id,
                title=f"Order #{instance.id} Update",
                message=message,
                notification_type="order_update",
                related_object_id=instance.id,
                related_object_type="order"
            )
            
            # Notify seller (except for buyer-initiated status changes)
            if instance.status not in ['cancelled']:  # Cancelled might be buyer-initiated
                send_generic_notification_task.delay(
                    user_id=instance.seller.id,
                    title=f"Order #{instance.id} Update",
                    message=f"Order status updated to {instance.status}",
                    notification_type="order_update",
                    related_object_id=instance.id,
                    related_object_type="order"
                )
            
            # Clear cache
            _order_status_cache.pop(instance.pk, None)
    except Exception as e:
        logger.error(f"Error sending order status change notification: {e}")


# ─── SUPPORT REQUEST NOTIFICATIONS ──────────────────────────────────────────

@receiver(post_save, sender=SupportRequest)
def notify_on_support_request(sender, instance, created, **kwargs):
    """Notify admins when a support request is created"""
    if created:
        try:
            notification_service = get_notification_service()
            
            # Notify all admins
            admins = User.objects.filter(is_staff=True, is_active=True)
            for admin in admins:
                send_generic_notification_task.delay(
                    user_id=admin.id,
                    title="New Support Request 🆘",
                    message=f"{instance.user.get_full_name() or instance.user.username} submitted a support request: {instance.subject}",
                    notification_type="support",
                    related_object_id=instance.id,
                    related_object_type="support_request"
                )
            
            # Notify user that their request was received
            send_generic_notification_task.delay(
                user_id=instance.user.id,
                title="Support Request Received",
                message=f"Your support request '{instance.subject}' has been received. We'll get back to you soon.",
                notification_type="support",
                related_object_id=instance.id,
                related_object_type="support_request"
            )
        except Exception as e:
            logger.error(f"Error sending support request notification: {e}")


@receiver(post_save, sender=SupportRequest)
def notify_on_support_status_change(sender, instance, **kwargs):
    """Notify user when support request status changes"""
    try:
        # Check if status changed (this is a simplified check)
        # In production, you might want to track previous status like we do for orders
        if instance.status in ['in_progress', 'resolved', 'closed']:
            notification_service = get_notification_service()
            
            status_messages = {
                'in_progress': "Your support request is being reviewed",
                'resolved': "Your support request has been resolved",
                'closed': "Your support request has been closed",
            }
            
            message = status_messages.get(instance.status, f"Support request status updated to {instance.status}")
            
            send_generic_notification_task.delay(
                user_id=instance.user.id,
                title=f"Support Request Update",
                message=message,
                notification_type="support_update",
                related_object_id=instance.id,
                related_object_type="support_request"
            )
    except Exception as e:
        logger.error(f"Error sending support status change notification: {e}")


# ─── REVIEW NOTIFICATIONS ───────────────────────────────────────────────────

@receiver(post_save, sender=Review)
def notify_on_review_created(sender, instance, created, **kwargs):
    """Notify seller when a review is created"""
    if created:
        try:
            notification_service = get_notification_service()
            
            # Notify seller
            buyer_name = instance.buyer.get_full_name() or instance.buyer.username
            rating_stars = "⭐" * instance.rating
            
            send_generic_notification_task.delay(
                user_id=instance.seller.id,
                title="New Review Received! ⭐",
                message=f"{buyer_name} left a {rating_stars} review for your listing: {instance.listing.title if instance.listing else 'Order'}",
                notification_type="review",
                related_object_id=instance.id,
                related_object_type="review"
            )
        except Exception as e:
            logger.error(f"Error sending review notification: {e}")


# Track previous seller_reply to detect new replies
_review_reply_cache = {}

@receiver(pre_save, sender=Review)
def cache_review_reply(sender, instance, **kwargs):
    """Cache seller_reply before save to detect new replies"""
    if instance.pk:
        try:
            old_instance = Review.objects.get(pk=instance.pk)
            _review_reply_cache[instance.pk] = old_instance.seller_reply
        except Review.DoesNotExist:
            _review_reply_cache[instance.pk] = None

@receiver(post_save, sender=Review)
def notify_on_review_reply(sender, instance, created, **kwargs):
    """Notify buyer when seller replies to their review"""
    if not created and instance.seller_reply:
        try:
            old_reply = _review_reply_cache.get(instance.pk)
            
            # Only notify if seller_reply was just added (was empty/None, now has content)
            if old_reply != instance.seller_reply and (not old_reply or old_reply.strip() == '') and instance.seller_reply.strip():
                notification_service = get_notification_service()
                
                seller_name = instance.seller.get_full_name() or instance.seller.username
                
                send_generic_notification_task.delay(
                    user_id=instance.buyer.id,
                    title="Seller Replied to Your Review! 💬",
                    message=f"{seller_name} replied to your review for {instance.listing.title if instance.listing else 'your order'}",
                    notification_type="review_reply",
                    related_object_id=instance.id,
                    related_object_type="review"
                )
            
            # Clear cache
            _review_reply_cache.pop(instance.pk, None)
        except Exception as e:
            logger.error(f"Error sending review reply notification: {e}")
