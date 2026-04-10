"""
commerce.services.review
-----------------------
Service for handling order reviews and ratings.
Ensures that reviews are only created for completed/delivered orders
with released escrow funds.
"""
import logging
from rest_framework.exceptions import ValidationError, PermissionDenied
from commerce.models import Order
from escrow_engine.state_machine import TransactionStatus
from trust.serializers import CreateReviewSerializer, ReviewSerializer
from trust.services import update_seller_rating

logger = logging.getLogger(__name__)

def create_order_review(order: Order, user, rating, comment=''):
    """
    Create a review for an order and update the seller's rating.
    
    Validates:
    - User is the buyer.
    - Review doesn't already exist.
    - Order status is 'delivered' or 'completed'.
    - Escrow status is RELEASED.
    """
    # 1. Check if user is the buyer
    if order.buyer != user:
        raise PermissionDenied("Only the buyer of this order can leave a review.")
    
    # 2. Check if review already exists
    if hasattr(order, 'review'):
        raise ValidationError("A review already exists for this order.")
    
    # 3. Validate order status — only after the order is completed (funds / lifecycle settled)
    if order.status != 'completed':
        raise ValidationError(
            f"Order must be completed to leave a review. Current: {order.status}"
        )
    
    # 4. Validate escrow status
    txn = getattr(order, 'engine_transaction', None)
    if not txn:
        # Fallback to older related name if exists, but engine_transaction is standard now
        from escrow_engine.models import Transaction
        txn = Transaction.objects.filter(linked_order=order).first()

    if not txn:
        raise ValidationError("Order must have an associated escrow transaction.")
    
    if txn.status != TransactionStatus.RELEASED:
        raise ValidationError(
            f"Escrow must be {TransactionStatus.RELEASED} to leave a review. "
            f"Current engine status: {txn.status}"
        )
    
    # 5. Create review using serializer for consistency
    serializer = CreateReviewSerializer(data={
        'order': order.id,
        'buyer': user.id,
        'rating': rating,
        'comment': comment
    })
    
    if not serializer.is_valid():
        raise ValidationError(serializer.errors)
    
    review = serializer.save()
    
    # 6. Update seller rating
    update_seller_rating(order.seller)
    
    # 7. Return serialized review data
    review.refresh_from_db()
    return ReviewSerializer(review).data
