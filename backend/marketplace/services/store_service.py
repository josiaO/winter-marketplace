"""
Store lifecycle: slugs, default store creation, sync from seller profile, statistics.
"""
from __future__ import annotations

import logging
import uuid

from django.db import IntegrityError, transaction
from django.utils.crypto import get_random_string
from django.utils.text import slugify

from commerce.models import Order
from listings.models import Listing
from marketplace.models import SellerProfile, Store

logger = logging.getLogger(__name__)


def unique_store_slug(base: str) -> str:
    """
    Generate a unique slug within max_length=200, resilient to races (random suffix).
    """
    raw = slugify(base) or 'store'
    raw = raw[:80]
    for _ in range(64):
        suffix = get_random_string(8).lower()
        candidate = f'{raw}-{suffix}'[:200]
        if not Store.objects.filter(slug=candidate).exists():
            return candidate
    return f'{raw[:160]}-{uuid.uuid4().hex}'[:200]


@transaction.atomic
def ensure_default_store_for_seller(seller: SellerProfile) -> Store | None:
    locked = (
        Store.objects.select_for_update()
        .filter(seller=seller)
        .order_by('id')
        .first()
    )
    if locked:
        return locked

    user = seller.user
    username = user.get_username() or f'user-{user.pk}'
    name = (seller.business_name or seller.store_name or '').strip()
    if not name:
        name = f"{username}'s store"

    buyer_visible = seller.verification_status == 'verified' and seller.is_active

    for attempt in range(8):
        slug = unique_store_slug(f'{username}-{seller.pk}-{attempt}')
        try:
            return Store.objects.create(
                seller=seller,
                name=name[:200],
                slug=slug,
                description=(seller.store_description or '')[:2000],
                is_active=buyer_visible,
            )
        except IntegrityError:
            logger.warning('Store slug collision on create, retrying (attempt %s)', attempt)
            continue
    return None


def sync_store_from_seller_profile(seller: SellerProfile) -> None:
    store = seller.stores.order_by('id').first()
    if store is None:
        store = ensure_default_store_for_seller(seller)
    if store is None:
        return

    display_name = (seller.store_name or seller.business_name or store.name or '').strip()
    if display_name:
        store.name = display_name[:200]
    if seller.store_description is not None:
        store.description = seller.store_description

    if seller.store_logo:
        store.logo = seller.store_logo
    if seller.store_banner:
        store.banner = seller.store_banner

    store.is_active = seller.verification_status == 'verified' and seller.is_active
    store.save(update_fields=['name', 'description', 'logo', 'banner', 'is_active', 'updated_at'])


def update_store_statistics(store: Store) -> Store:
    store.total_listings = Listing.objects.filter(
        owner=store.seller.user,
        is_published=True,
    ).count()
    store.total_sales = Order.objects.filter(
        seller=store.seller.user,
        status='completed',
    ).count()
    store.save(update_fields=['total_listings', 'total_sales', 'updated_at'])
    return store
