"""
Buyer–seller listing offers (in-platform negotiation).
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from listings.models import Listing

from .models import ListingOffer
from .serializers import ListingOfferSerializer
from .seller_notifications import (
    notify_buyer_offer_accepted,
    notify_buyer_offer_countered,
    notify_buyer_offer_declined,
    notify_seller_new_offer,
    notify_seller_offer_buyer_countered,
)

MAX_ACTIVE_OFFERS = 3
MAX_COUNTER_ROUNDS = 3

_ACTIVE = (
    ListingOffer.Status.AWAITING_SELLER,
    ListingOffer.Status.AWAITING_BUYER,
    ListingOffer.Status.ACCEPTED,
)


def _active_offer_count(buyer_id: int) -> int:
    return ListingOffer.objects.filter(buyer_id=buyer_id, status__in=_ACTIVE).count()


class ListingOfferViewSet(viewsets.ModelViewSet):
    """
    GET /commerce/offers/ — mine (buyer or seller role via ?role=)
    POST /commerce/offers/ — buyer creates offer
    POST /commerce/offers/{id}/seller-respond/
    POST /commerce/offers/{id}/buyer-respond/
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ListingOfferSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        u = self.request.user
        role = (self.request.query_params.get('role') or '').strip().lower()
        qs = ListingOffer.objects.select_related('listing', 'buyer', 'seller').order_by('-created_at')
        if role == 'seller':
            return qs.filter(seller=u)
        return qs.filter(buyer=u)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        listing_id = request.data.get('listing_id')
        amount_raw = request.data.get('amount')
        note = (request.data.get('note') or '').strip()[:2000]
        if not listing_id:
            return Response({'error': 'listing_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            amount = Decimal(str(amount_raw).strip())
        except (InvalidOperation, TypeError, ValueError):
            return Response({'error': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)

        listing = Listing.objects.select_related('owner').filter(pk=listing_id, is_published=True).first()
        if not listing or not listing.owner_id:
            return Response({'error': 'Listing not available.'}, status=status.HTTP_400_BAD_REQUEST)
        if listing.owner_id == request.user.id:
            return Response({'error': 'You cannot make an offer on your own listing.'}, status=status.HTTP_400_BAD_REQUEST)

        listed = listing.price
        if listed is None or listed <= 0:
            return Response({'error': 'Listing has no valid price.'}, status=status.HTTP_400_BAD_REQUEST)

        min_offer = listed * Decimal('0.5')
        max_offer = listed * Decimal('0.99')
        if amount < min_offer or amount > max_offer:
            return Response(
                {'error': 'Offer must be between 50% and 99% of the listed price.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if _active_offer_count(request.user.id) >= MAX_ACTIVE_OFFERS:
            return Response(
                {'error': 'You can have at most 3 active offers at a time.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ListingOffer.objects.filter(
            buyer=request.user,
            listing=listing,
            status__in=(
                ListingOffer.Status.AWAITING_SELLER,
                ListingOffer.Status.AWAITING_BUYER,
            ),
        ).update(status=ListingOffer.Status.SUPERSEDED)

        offer = ListingOffer.objects.create(
            listing=listing,
            buyer=request.user,
            seller=listing.owner,
            status=ListingOffer.Status.AWAITING_SELLER,
            listed_price=listed,
            current_amount=amount,
            buyer_note=note,
            last_actor='buyer',
            counter_round=0,
        )
        notify_seller_new_offer(offer)
        return Response(ListingOfferSerializer(offer).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='seller-respond')
    @transaction.atomic
    def seller_respond(self, request, pk=None):
        offer = self.get_object()
        if offer.seller_id != request.user.id:
            return Response({'error': 'Only the seller can respond here.'}, status=status.HTTP_403_FORBIDDEN)
        if offer.status != ListingOffer.Status.AWAITING_SELLER:
            return Response({'error': 'This offer is not awaiting your response.'}, status=status.HTTP_400_BAD_REQUEST)

        action_name = (request.data.get('action') or '').strip().lower()
        if action_name == 'accept':
            offer.status = ListingOffer.Status.ACCEPTED
            offer.accepted_until = timezone.now() + timedelta(hours=2)
            offer.last_actor = 'seller'
            offer.save()
            notify_buyer_offer_accepted(offer)
            return Response(ListingOfferSerializer(offer).data)
        if action_name == 'decline':
            offer.status = ListingOffer.Status.DECLINED
            offer.last_actor = 'seller'
            offer.save()
            notify_buyer_offer_declined(offer, by='seller')
            return Response(ListingOfferSerializer(offer).data)
        if action_name == 'counter':
            if offer.counter_round >= MAX_COUNTER_ROUNDS:
                return Response(
                    {'error': 'Maximum negotiation rounds reached. Accept or decline.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                new_amt = Decimal(str(request.data.get('amount', '')).strip())
            except (InvalidOperation, TypeError, ValueError):
                return Response({'error': 'Invalid counter amount.'}, status=status.HTTP_400_BAD_REQUEST)
            listed = offer.listed_price
            min_offer = listed * Decimal('0.5')
            max_offer = listed * Decimal('0.99')
            if new_amt < min_offer or new_amt > max_offer:
                return Response(
                    {'error': 'Counter must stay between 50% and 99% of the listed price.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            offer.current_amount = new_amt
            offer.seller_note = (request.data.get('note') or '').strip()[:2000]
            offer.status = ListingOffer.Status.AWAITING_BUYER
            offer.last_actor = 'seller'
            offer.counter_round += 1
            offer.save()
            notify_buyer_offer_countered(offer)
            return Response(ListingOfferSerializer(offer).data)

        return Response({'error': 'action must be accept, decline, or counter.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='buyer-respond')
    @transaction.atomic
    def buyer_respond(self, request, pk=None):
        offer = self.get_object()
        if offer.buyer_id != request.user.id:
            return Response({'error': 'Only the buyer can respond here.'}, status=status.HTTP_403_FORBIDDEN)
        if offer.status != ListingOffer.Status.AWAITING_BUYER:
            return Response({'error': 'This offer is not awaiting your response.'}, status=status.HTTP_400_BAD_REQUEST)

        action_name = (request.data.get('action') or '').strip().lower()
        if action_name == 'accept':
            offer.status = ListingOffer.Status.ACCEPTED
            offer.accepted_until = timezone.now() + timedelta(hours=2)
            offer.last_actor = 'buyer'
            offer.save()
            notify_buyer_offer_accepted(offer, accepted_own_counter=True)
            return Response(ListingOfferSerializer(offer).data)
        if action_name == 'decline':
            offer.status = ListingOffer.Status.DECLINED
            offer.last_actor = 'buyer'
            offer.save()
            notify_buyer_offer_declined(offer, by='buyer')
            return Response(ListingOfferSerializer(offer).data)
        if action_name == 'counter':
            if offer.counter_round >= MAX_COUNTER_ROUNDS:
                return Response(
                    {'error': 'Maximum negotiation rounds reached. Accept or decline.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                new_amt = Decimal(str(request.data.get('amount', '')).strip())
            except (InvalidOperation, TypeError, ValueError):
                return Response({'error': 'Invalid counter amount.'}, status=status.HTTP_400_BAD_REQUEST)
            listed = offer.listed_price
            min_offer = listed * Decimal('0.5')
            max_offer = listed * Decimal('0.99')
            if new_amt < min_offer or new_amt > max_offer:
                return Response(
                    {'error': 'Counter must stay between 50% and 99% of the listed price.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            offer.current_amount = new_amt
            offer.buyer_note = (request.data.get('note') or '').strip()[:2000]
            offer.status = ListingOffer.Status.AWAITING_SELLER
            offer.last_actor = 'buyer'
            offer.counter_round += 1
            offer.save()
            notify_seller_offer_buyer_countered(offer)
            return Response(ListingOfferSerializer(offer).data)

        return Response({'error': 'action must be accept, decline, or counter.'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='active-count')
    def active_count(self, request):
        return Response({'active_count': _active_offer_count(request.user.id), 'max': MAX_ACTIVE_OFFERS})
