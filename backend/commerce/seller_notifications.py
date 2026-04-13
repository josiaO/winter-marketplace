"""
Seller-facing push + in-app notifications (Swahili / English).

Copy aligns with marketplace seller spec. Payment is always before shipment
(no pay-on-delivery): new-order copy stresses awaiting buyer payment.
"""
from __future__ import annotations

import logging
from typing import Any

from communications.notification_service import get_notification_service

logger = logging.getLogger(__name__)


def _seller_lang(user) -> str:
    prof = getattr(user, 'profile', None)
    if not prof:
        return 'sw'
    lang = getattr(prof, 'seller_notification_language', None) or 'sw'
    return lang if lang in ('sw', 'en') else 'sw'


def _tzs(amount) -> str:
    try:
        n = float(amount)
    except (TypeError, ValueError):
        n = 0.0
    s = f"{n:,.0f}"
    return f"TZS {s}"


def _buyer_name(order) -> str:
    b = order.buyer
    if not b:
        return 'Buyer'
    parts = [b.first_name or '', b.last_name or '']
    name = ' '.join(p for p in parts if p).strip()
    return name or getattr(b, 'username', None) or 'Buyer'


def _first_item_title(order) -> str:
    it = order.items.first() if hasattr(order, 'items') else None
    if not it:
        return 'item'
    if getattr(it, 'listing_title', None):
        return it.listing_title
    listing = getattr(it, 'listing', None)
    if listing is not None and hasattr(listing, 'title'):
        return listing.title or 'item'
    return 'item'


def _push_seller(
    user,
    *,
    title_sw: str,
    title_en: str,
    body_sw: str,
    body_en: str,
    notification_type: str,
    extra_data: dict[str, Any] | None = None,
    related_object_id: int | None = None,
    related_object_type: str | None = None,
    send_push: bool = True,
) -> None:
    lang = _seller_lang(user)
    title = title_sw if lang == 'sw' else title_en
    body = body_sw if lang == 'sw' else body_en
    try:
        get_notification_service().notify_generic(
            user=user,
            title=title,
            message=body,
            notification_type=notification_type,
            related_object_id=related_object_id,
            related_object_type=related_object_type,
            send_push=send_push,
            extra_data=extra_data,
        )
    except Exception:
        logger.exception('seller push failed user=%s type=%s', getattr(user, 'id', None), notification_type)


def notify_seller_new_order_pending_payment(order) -> None:
    """Order exists but is unpaid — ship only after payment clears."""
    buyer = _buyer_name(order)
    product = _first_item_title(order)
    amt = _tzs(order.total_amount)
    oid = order.id
    title_sw = '🛒 Agizo Jipya!'
    title_en = '🛒 New order!'
    body_sw = f'{buyer} ameagiza {product} — {amt}. Subiri malipo kabla ya kutuma.'
    body_en = f'{buyer} placed an order for {product} — {amt}. Await payment before shipping.'
    _push_seller(
        order.seller,
        title_sw=title_sw,
        title_en=title_en,
        body_sw=body_sw,
        body_en=body_en,
        notification_type='order',
        related_object_id=oid,
        related_object_type='order',
        extra_data={'deep_link': f'/seller/orders/{oid}'},
    )


def notify_seller_payment_in_escrow(order) -> None:
    buyer = _buyer_name(order)
    product = _first_item_title(order)
    amt = _tzs(order.total_amount)
    oid = order.id
    _push_seller(
        order.seller,
        title_sw='💰 Malipo Yamepokelewa',
        title_en='💰 Payment received',
        body_sw=f'{amt} iko salama kwenye escrow. Tuma {product} kwa {buyer}.',
        body_en=f'{amt} is held in escrow. Ship {product} to {buyer}.',
        notification_type='order',
        related_object_id=oid,
        related_object_type='order',
        extra_data={'deep_link': f'/seller/orders/{oid}'},
    )


def notify_seller_funds_released(order) -> None:
    amt = _tzs(order.total_amount)
    oid = order.id
    _push_seller(
        order.seller,
        title_sw='✅ Pesa Zimeachiwa!',
        title_en='✅ Funds released!',
        body_sw=f'{amt} sasa iko tayari kuondoa. Agizo #{oid} limekamilika.',
        body_en=f'{amt} is ready to withdraw. Order #{oid} is complete.',
        notification_type='payout',
        related_object_id=oid,
        related_object_type='order',
        extra_data={'deep_link': '/seller/wallet'},
    )


def notify_seller_dispute(order) -> None:
    buyer = _buyer_name(order)
    oid = order.id
    _push_seller(
        order.seller,
        title_sw='⚠️ Mnunuzi Amefungua Mgogoro',
        title_en='⚠️ Buyer opened a dispute',
        body_sw=f'{buyer} hana furaha na agizo #{oid}. Angalia na ujibu haraka.',
        body_en=f'{buyer} opened a dispute on order #{oid}. Review and respond quickly.',
        notification_type='dispute',
        related_object_id=oid,
        related_object_type='order',
        extra_data={'deep_link': f'/seller/orders/{oid}/dispute'},
    )


def notify_seller_new_review(seller, buyer, rating: int, listing_id: int | None) -> None:
    bname = buyer.get_full_name() or buyer.username
    _push_seller(
        seller,
        title_sw='⭐ Tathmini Mpya',
        title_en='⭐ New review',
        body_sw=f'{bname} amekupa nyota {rating}/5',
        body_en=f'{bname} gave you {rating}/5 stars',
        notification_type='review',
        related_object_id=listing_id,
        related_object_type='listing' if listing_id else None,
        extra_data={'deep_link': '/seller/reviews', 'rating': str(rating)},
    )


def notify_seller_low_stock(seller, listing_title: str, count: int, listing_id: int) -> None:
    _push_seller(
        seller,
        title_sw='📦 Bidhaa Karibu Kwisha',
        title_en='📦 Low stock',
        body_sw=f'{listing_title} imebaki {count} tu. Ongeza stoki sasa.',
        body_en=f'{listing_title} has only {count} left. Restock now.',
        notification_type='inventory',
        related_object_id=listing_id,
        related_object_type='listing',
        extra_data={'deep_link': f'/seller/listings/{listing_id}/edit', 'count': str(count)},
    )


def notify_seller_new_offer(offer) -> None:
    buyer = offer.buyer.get_full_name().strip() or offer.buyer.username
    title = offer.listing.title if offer.listing else 'your listing'
    _push_seller(
        offer.seller,
        title_sw='💬 Ofaa Kutoka Mnunuzi',
        title_en='💬 New buyer offer',
        body_sw=f'{buyer} ametoa {_tzs(offer.current_amount)} kwa {title} (iliyoorodheshwa {_tzs(offer.listed_price)}).',
        body_en=f'{buyer} offered {_tzs(offer.current_amount)} for {title} (listed at {_tzs(offer.listed_price)}).',
        notification_type='offer',
        related_object_id=offer.listing_id,
        related_object_type='listing',
        extra_data={'deep_link': f'/seller/listings/{offer.listing_id}/edit', 'offer_id': str(offer.id)},
    )


def notify_buyer_offer_accepted(offer, *, accepted_own_counter: bool = False) -> None:
    title = offer.listing.title if offer.listing else 'your item'
    if accepted_own_counter:
        msg = f'You agreed on {_tzs(offer.current_amount)} for {title}. Complete checkout within 2 hours.'
        ttl = 'Price agreed'
    else:
        msg = f'You can buy {title} at {_tzs(offer.current_amount)} for the next 2 hours.'
        ttl = 'Offer accepted — complete checkout'
    get_notification_service().notify_generic(
        user=offer.buyer,
        title=ttl,
        message=msg,
        notification_type='offer',
        related_object_id=offer.listing_id,
        related_object_type='listing',
        send_push=True,
        extra_data={
            'deep_link': f'/products/{offer.listing_id}',
            'offer_id': str(offer.id),
            'checkout_hint': True,
        },
    )


def notify_buyer_offer_declined(offer, *, by: str) -> None:
    title = offer.listing.title if offer.listing else 'Listing'
    if by == 'seller':
        get_notification_service().notify_generic(
            user=offer.buyer,
            title='Offer update',
            message=f'The seller declined the negotiation for {title}.',
            notification_type='offer',
            related_object_id=offer.listing_id,
            related_object_type='listing',
            send_push=True,
            extra_data={'deep_link': f'/products/{offer.listing_id}'},
        )
        return
    buyer = offer.buyer.get_full_name().strip() or offer.buyer.username
    _push_seller(
        offer.seller,
        title_sw='💬 Ofaa Imekataliwa',
        title_en='💬 Offer declined',
        body_sw=f'{buyer} amekataa ofaa ya {title}.',
        body_en=f'{buyer} declined the offer for {title}.',
        notification_type='offer',
        related_object_id=offer.listing_id,
        related_object_type='listing',
        extra_data={'deep_link': f'/seller/listings/{offer.listing_id}/edit'},
    )


def notify_buyer_offer_countered(offer) -> None:
    sn = offer.seller.get_full_name().strip() or offer.seller.username
    title = offer.listing.title if offer.listing else 'item'
    get_notification_service().notify_generic(
        user=offer.buyer,
        title='Counter-offer',
        message=f'{sn} countered with {_tzs(offer.current_amount)} for {title}.',
        notification_type='offer',
        related_object_id=offer.listing_id,
        related_object_type='listing',
        send_push=True,
        extra_data={'deep_link': f'/products/{offer.listing_id}', 'offer_id': str(offer.id)},
    )


def notify_seller_offer_buyer_countered(offer) -> None:
    buyer = offer.buyer.get_full_name().strip() or offer.buyer.username
    title = offer.listing.title if offer.listing else 'listing'
    _push_seller(
        offer.seller,
        title_sw='💬 Mnunuzi Amejibu Ofaa',
        title_en='💬 Buyer countered your offer',
        body_sw=f'{buyer} amependekeza {_tzs(offer.current_amount)} kwa {title}.',
        body_en=f'{buyer} countered with {_tzs(offer.current_amount)} for {title}.',
        notification_type='offer',
        related_object_id=offer.listing_id,
        related_object_type='listing',
        extra_data={'deep_link': f'/seller/listings/{offer.listing_id}/edit', 'offer_id': str(offer.id)},
    )


def notify_buyer_payment_confirmed_order(order) -> None:
    """Buyer: payment recorded — seller will ship (no 'seller clicked confirm' wording)."""
    oid = order.id
    get_notification_service().notify_generic(
        user=order.buyer,
        title='Payment received',
        message=f'We received your payment for order #{oid}. The seller will ship your items.',
        notification_type='order',
        related_object_id=oid,
        related_object_type='order',
        send_push=True,
        extra_data={'deep_link': f'/orders/{oid}'},
    )
