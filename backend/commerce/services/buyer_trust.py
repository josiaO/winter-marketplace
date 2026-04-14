"""
Aggregated seller trust signals for buyer-facing listing detail (behavioral data).
"""
from __future__ import annotations

from datetime import timedelta
from django.db.models import Count, Q
from django.utils import timezone

from commerce.models import Order
from communications.models import Conversation, Message


def _format_relative_short(delta: timedelta) -> str:
    secs = int(delta.total_seconds())
    if secs < 3600:
        m = max(1, secs // 60)
        return f'{m} minute{"s" if m != 1 else ""}'
    if secs < 86400:
        h = max(1, secs // 3600)
        return f'{h} hour{"s" if h != 1 else ""}'
    d = secs // 86400
    return f'{d} day{"s" if d != 1 else ""}'


def seller_avg_response_time_hours(seller_id: int) -> float | None:
    """
    Median hours for seller to provide their VERY FIRST reply to a new conversation.
    This is the strongest indicator of reliability for guest buyers.
    """
    convs = Conversation.objects.filter(seller_id=seller_id, is_active=True).only('id')[:500]
    if not convs.exists():
        return None

    deltas = []
    for conv in convs:
        # Get first buyer message
        first_buyer = Message.objects.filter(
            conversation=conv, 
            is_deleted=False
        ).exclude(sender_id=seller_id).order_by('created_at').first()
        
        if not first_buyer:
            continue
            
        # Get first seller response AFTER that buyer message
        first_reply = Message.objects.filter(
            conversation=conv,
            sender_id=seller_id,
            is_deleted=False,
            created_at__gt=first_buyer.created_at
        ).order_by('created_at').first()
        
        if first_reply:
            deltas.append((first_reply.created_at - first_buyer.created_at).total_seconds() / 3600.0)

    if not deltas:
        return None
        
    deltas.sort()
    mid = len(deltas) // 2
    if len(deltas) % 2:
        return float(deltas[mid])
    return float((deltas[mid - 1] + deltas[mid]) / 2.0)


def build_seller_trust_block(listing) -> dict:
    """
    Trust card payload for product pages (public).
    """
    empty = {
        'seller_name': None,
        'store_name': None,
        'seller_verified_badge': False,
        'identity_verified': False,
        'completion_rate_pct': None,
        'completion_bar_tier': 'neutral',
        'last_shipped_text': None,
        'last_shipped_stale': False,
        'joined_text': None,
        'response_time_text': None,
        'completed_orders_count': 0,
        'seller_tier_label': 'New seller',
        'reviews_preview': [],
        'reviews_total': 0,
    }
    owner = getattr(listing, 'owner', None)
    if not owner:
        return empty

    from trust.models import Review, TrustScore

    seller_name = owner.get_full_name().strip() or owner.username
    store_name = None
    try:
        sp = owner.seller_profile
        if sp and sp.business_name:
            store_name = sp.business_name
    except Exception:
        pass

    trust_block = {'id_verified': False, 'fully_verified': False}
    try:
        ts = owner.trust_score
        trust_block['id_verified'] = bool(ts.id_verified)
        trust_block['fully_verified'] = bool(ts.id_verified and ts.tin_verified and ts.license_verified)
    except Exception:
        try:
            ts = TrustScore.objects.filter(user_id=owner.id).first()
            if ts:
                trust_block['id_verified'] = bool(ts.id_verified)
                trust_block['fully_verified'] = bool(
                    ts.id_verified and ts.tin_verified and ts.license_verified
                )
        except Exception:
            pass

    seller_verified_badge = trust_block['fully_verified']
    if not seller_verified_badge:
        try:
            if hasattr(owner, 'seller_profile') and owner.seller_profile.is_verified:
                seller_verified_badge = True
        except Exception:
            pass

    qs = Order.objects.filter(seller=owner).exclude(status='pending')
    total = qs.count()
    completed = qs.filter(status__in=['completed', 'delivered']).count()
    failed = qs.filter(status__in=['disputed', 'refunded', 'cancelled']).count()
    denom = max(1, completed + failed)
    completion_pct = round(100.0 * completed / denom, 1) if total else None

    if completion_pct is None:
        tier = 'neutral'
    elif completion_pct >= 90:
        tier = 'high'
    elif completion_pct >= 75:
        tier = 'mid'
    else:
        tier = 'low'

    last_shipped = (
        Order.objects.filter(seller=owner, shipped_at__isnull=False)
        .order_by('-shipped_at')
        .values_list('shipped_at', flat=True)
        .first()
    )
    now = timezone.now()
    last_shipped_text = None
    stale = False
    if last_shipped:
        delta = now - last_shipped
        last_shipped_text = f'Last order shipped {_format_relative_short(delta)} ago'
        stale = delta > timedelta(days=30)
    elif total == 0:
        last_shipped_text = 'No shipped orders yet'

    joined = owner.date_joined
    age = now - joined
    if age.days >= 365:
        joined_text = f'Joined {age.days // 365} year{"s" if age.days // 365 != 1 else ""} ago'
    elif age.days >= 30:
        joined_text = f'Joined {age.days // 30} months ago'
    else:
        joined_text = f'Joined {max(1, age.days)} days ago'

    med_h = seller_avg_response_time_hours(owner.id)
    if med_h is None:
        response_time_text = None
    elif med_h < 1:
        response_time_text = f'Usually replies within {max(1, int(med_h * 60))} minutes'
    else:
        response_time_text = f'Usually replies within {max(1, round(med_h))} hours'

    completed_orders_count = qs.filter(status__in=['completed', 'delivered']).count()
    if completed_orders_count < 5:
        tier_label = 'New seller'
    elif completed_orders_count <= 20:
        tier_label = 'Growing seller'
    else:
        tier_label = str(completed_orders_count)

    rev_qs = (
        Review.objects.filter(listing=listing, is_approved=True, is_hidden=False)
        .select_related('buyer', 'order')
        .prefetch_related('media')
        .annotate(_mc=Count('media', filter=Q(media__id__isnull=False)))
        .order_by('-_mc', '-created_at')
    )
    reviews_total = rev_qs.count()
    preview = []
    for r in rev_qs[:2]:
        buyer = r.buyer
        fn = (buyer.first_name or '').strip() or buyer.username
        ln = (buyer.last_name or '').strip()
        initial = f'{ln[0]}.' if ln else ''
        media_urls = []
        for m in r.media.all()[:3]:
            try:
                if m.file:
                    media_urls.append(m.file.url)
            except Exception:
                pass
        variant_bits = []
        try:
            first_item = r.order.items.select_related('listing').first()
            if first_item and first_item.listing_id == listing.id:
                # variant summary from price_at_time + quantity only; specs row lives on listing snapshot
                variant_bits.append(f'Qty {first_item.quantity}')
        except Exception:
            pass
        preview.append(
            {
                'id': r.id,
                'rating': r.rating,
                'buyer_display': f'{fn} {initial}'.strip(),
                'created_at': r.created_at.isoformat(),
                'comment': r.comment,
                'seller_reply': r.seller_reply or '',
                'verified_purchase': True,
                'variant_summary': ', '.join(variant_bits) if variant_bits else None,
                'media_urls': media_urls,
            }
        )

    # Rating breakdown
    breakdown = {i: 0 for i in range(1, 6)}
    breakdown_qs = (
        Review.objects.filter(listing=listing, is_approved=True, is_hidden=False)
        .values('rating')
        .annotate(count=Count('id'))
    )
    for row in breakdown_qs:
        breakdown[row['rating']] = row['count']

    return {
        'seller_name': seller_name,
        'store_name': store_name,
        'seller_verified_badge': seller_verified_badge,
        'identity_verified': trust_block['id_verified'],
        'completion_rate_pct': completion_pct,
        'completion_bar_tier': tier,
        'last_shipped_text': last_shipped_text,
        'last_shipped_stale': stale,
        'joined_text': joined_text,
        'response_time_text': response_time_text,
        'completed_orders_count': completed_orders_count,
        'seller_tier_label': tier_label,
        'reviews_preview': preview,
        'reviews_total': reviews_total,
        'rating_breakdown': breakdown,
    }
