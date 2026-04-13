"""
commerce.services.stats
----------------------
Service for calculating seller statistics and financial summaries.
Includes revenue, order counts, and escrow status.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum, Count
from django.utils import timezone
from commerce.models import Order
from escrow_engine.models import Transaction, TransactionStatus, Payout as EngPayout

logger = logging.getLogger(__name__)

def get_seller_stats(user):
    """
    Returns stats specifically for seller's orders and finances.
    
    Includes:
    - Order counts by status.
    - Revenue (total, today, this month).
    - Platform fees and net earnings.
    - Escrow status from engine.
    - Payout status from engine.
    """
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_start = (month_start - timedelta(days=1)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    seller_orders = Order.objects.filter(seller=user)
    
    # 1. Order counts by status
    order_counts_qs = seller_orders.values('status').annotate(count=Count('id'))
    order_counts = {item['status']: item['count'] for item in order_counts_qs}
    
    # 2. Revenue calculation
    # We define revenue as being from 'delivered' or 'completed' orders
    delivered_orders = seller_orders.filter(status__in=['delivered', 'completed'])
    total_revenue = delivered_orders.aggregate(Sum('subtotal'))['subtotal__sum'] or Decimal('0')
    revenue_today = delivered_orders.filter(updated_at__gte=today_start).aggregate(Sum('subtotal'))['subtotal__sum'] or Decimal('0')
    revenue_this_month = delivered_orders.filter(updated_at__gte=month_start).aggregate(Sum('subtotal'))['subtotal__sum'] or Decimal('0')
    revenue_last_month = delivered_orders.filter(
        updated_at__gte=prev_month_start,
        updated_at__lt=month_start,
    ).aggregate(Sum('subtotal'))['subtotal__sum'] or Decimal('0')
    
    # 3. Platform fees and net earnings
    total_platform_fees = delivered_orders.aggregate(Sum('platform_fee'))['platform_fee__sum'] or Decimal('0')
    # Using Decimal for precise financial calculations
    net_earnings = total_revenue - total_platform_fees
    
    # 4. Escrow data from engine (HOLD, RELEASED, DISPUTED)
    try:
        escrow_summary = Transaction.objects.filter(
            seller_user=user
        ).values('status').annotate(total_amount=Sum('amount'))
        
        escrow_stats = {
            'held': Decimal('0'),
            'released': Decimal('0'),
            'disputed': Decimal('0')
        }
        
        for item in escrow_summary:
            status = item['status']
            amount = item['total_amount'] or Decimal('0')
            if status == TransactionStatus.HOLD:
                escrow_stats['held'] = amount
            elif status == TransactionStatus.RELEASED:
                escrow_stats['released'] = amount
            elif status == TransactionStatus.DISPUTED:
                escrow_stats['disputed'] = amount
    except Exception as e:
        logger.warning(f"Failed to fetch engine escrow data for seller {user.id}: {e}")
        escrow_stats = {'held': Decimal('0'), 'released': Decimal('0'), 'disputed': Decimal('0')}

    # 5. Payout data from engine (pending, completed)
    try:
        payout_summary = EngPayout.objects.filter(
            seller=user
        ).values('status').annotate(total_amount=Sum('amount'))
        
        payout_stats = {
            'pending': Decimal('0'),
            'completed': Decimal('0')
        }
        
        for item in payout_summary:
            status = item['status']
            amount = item['total_amount'] or Decimal('0')
            if status in ['pending', 'processing']:
                payout_stats['pending'] += amount
            elif status == 'completed':
                payout_stats['completed'] = amount
    except Exception as e:
        logger.warning(f"Failed to fetch engine payout data for seller {user.id}: {e}")
        payout_stats = {'pending': Decimal('0'), 'completed': Decimal('0')}
    
    return {
        'orders': {
            'new': order_counts.get('pending', 0),
            'awaiting_shipment': order_counts.get('confirmed', 0) + order_counts.get('processing', 0),
            'shipped': order_counts.get('shipped', 0),
            'delivered': order_counts.get('delivered', 0) + order_counts.get('completed', 0),
            'disputed': order_counts.get('disputed', 0),
            'cancelled': order_counts.get('cancelled', 0),
            'total': seller_orders.count(),
        },
        'revenue': {
            'today': float(revenue_today),
            'this_month': float(revenue_this_month),
            'last_month': float(revenue_last_month),
            'total': float(total_revenue),
            'net_earnings': float(net_earnings),
            'platform_fees_paid': float(total_platform_fees),
        },
        'policy': {
            'auto_confirm_receipt_days': int(getattr(settings, 'AUTO_CONFIRM_RECEIPT_DAYS', 7)),
        },
        'escrow': {
            'held': float(escrow_stats['held']),
            'released': float(escrow_stats['released']),
            'disputed': float(escrow_stats['disputed']),
            # Available for withdrawal = RELEASED funds - COMPLETED Payouts
            'available_for_withdrawal': float(escrow_stats['released'] - payout_stats['completed']),
        },
        'payouts': {
            'pending': float(payout_stats['pending']),
            'completed': float(payout_stats['completed']),
        }
    }
