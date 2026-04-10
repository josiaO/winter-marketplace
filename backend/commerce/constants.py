from django.db import models
from django.utils.translation import gettext_lazy as _

class OrderStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    CONFIRMED = 'confirmed', _('Confirmed')
    PROCESSING = 'processing', _('Processing')
    SHIPPED = 'shipped', _('Shipped')
    ARRIVED = 'arrived', _('Arrived')
    DELIVERED = 'delivered', _('Delivered')
    COMPLETED = 'completed', _('Completed')
    CANCELLED = 'cancelled', _('Cancelled')
    DISPUTED = 'disputed', _('Disputed')
    REFUNDED = 'refunded', _('Refunded')

class StockReservationStatus(models.TextChoices):
    RESERVED = 'reserved', _('Reserved')
    CONFIRMED = 'confirmed', _('Confirmed (Order Created)')
    RELEASED = 'released', _('Released')
    EXPIRED = 'expired', _('Expired')

class DeliveryStatus(models.TextChoices):
    PENDING = 'pending', _('Pending')
    PREPARING = 'preparing', _('Preparing')
    IN_TRANSIT = 'in_transit', _('In Transit')
    OUT_FOR_DELIVERY = 'out_for_delivery', _('Out for Delivery')
    DELIVERED = 'delivered', _('Delivered')
    FAILED = 'failed', _('Delivery Failed')
    RETURNED = 'returned', _('Returned')
