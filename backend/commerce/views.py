import logging
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Sum, Count
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied, MethodNotAllowed, ValidationError
from rest_framework.permissions import IsAdminUser

from .models import Cart, CartItem, Order, Wishlist, WishlistItem, StockReservation
from .serializers import (
    CartSerializer, OrderSerializer, WishlistSerializer, WishlistItemSerializer
)
from listings.models import Listing
from communications.notification_service import get_notification_service

# Services
from commerce.services.checkout import OrderService
from commerce.services.shipping_rates import list_shipping_options, shipping_cost_for_method
from .services.lifecycle import OrderLifecycleManager
from .services import cart_service as cart_svc
from .services.stats import get_seller_stats
from .services.review import create_order_review
from .services.payment_return import confirm_marketplace_payment_return
from .services.uploads import validate_commerce_upload_files
from escrow_engine.services.payout import process_payout as process_seller_payout

# Escrow Engine Integration
from escrow_engine.models import Transaction as EngTxn, Dispute as EngDispute, DisputeEvidence as EngDisputeEvidence, Payout as EngPayout
from escrow_engine.services.payment import initiate_payment, sync_buyer_contact_for_checkout
from escrow_engine.state_machine import TransactionStatus as _TS
from escrow_engine.providers.registry import should_open_payment_gateway
from escrow_engine.serializers import PayoutSerializer, TransactionSerializer as EngTxnSerializer

# Shared
# (selcom client moved to escrow_engine)

logger = logging.getLogger(__name__)

from .throttling import (
    CommerceCheckoutThrottle,
    CommerceDisputeThrottle,
    CommercePaymentInitiateThrottle,
    CommercePaymentReturnThrottle,
)


class CartViewSet(viewsets.ModelViewSet):
    """
    API endpoint for the user's shopping cart.
    """
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Cart.objects.none()
        return Cart.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        cart = cart_svc.get_or_create_cart(user=request.user)
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def add_item(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        listing_id = request.data.get('listing_id')
        quantity = int(request.data.get('quantity', 1))

        if not listing_id:
            return Response({'error': 'listing_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cart_item = cart_svc.add_to_cart(cart=cart, listing_id=listing_id, quantity=quantity)
            return Response(CartSerializer(cart).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def remove_item(self, request):
        cart = get_object_or_404(Cart, user=request.user)
        item_id = request.data.get('item_id')
        if not item_id:
            return Response({'error': 'item_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        CartItem.objects.filter(cart=cart, id=item_id).delete()
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=['get'])
    def shipping_options(self, request):
        """Return server-authoritative shipping methods and fees for checkout UI."""
        return Response({'options': list_shipping_options()})

    @action(detail=False, methods=['post'], throttle_classes=[CommerceCheckoutThrottle])
    def checkout(self, request):
        cart = get_object_or_404(Cart, user=request.user)
        shipping_address = request.data.get('shipping_address')
        if not shipping_address:
            return Response({'error': 'shipping_address is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        shipping_method = request.data.get('shipping_method', 'standard')
        try:
            shipping_cost_for_method(shipping_method)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        payment_method = request.data.get('payment_method', 'mobile_money')
        payment_channel = request.data.get('payment_channel', payment_method)

        try:
            # Ensure: if we need online payment and initiation fails, the order is NOT created.
            # This keeps "successful orders" aligned with payment actually starting.
            with transaction.atomic():
                orders = OrderService.create_order_from_cart(
                    cart=cart,
                    shipping_address=shipping_address,
                    shipping_method=shipping_method,
                    payment_method=payment_method,
                )

                # orders can be a single Order or a list of Orders
                if isinstance(orders, list):
                    serializer = OrderSerializer(orders, many=True)
                    primary_order = orders[0]
                else:
                    serializer = OrderSerializer(orders)
                    primary_order = orders

                response_data = serializer.data

                if should_open_payment_gateway(payment_method):
                    txn = EngTxn.objects.filter(linked_order=primary_order).first()
                    if not txn:
                        raise ValidationError("Payment could not be started (missing transaction). Order was not placed.")

                    # Source of Truth: escrow_engine owns Transaction writes; orchestration only here.
                    txn = sync_buyer_contact_for_checkout(
                        txn,
                        buyer_email=request.user.email or '',
                        buyer_phone=request.data.get('shipping_phone', '') or '',
                    )

                    result = initiate_payment(
                        txn,
                        actor=request.user,
                        payment_method=payment_method,
                        payment_channel=payment_channel,
                        buyer_phone=request.data.get('shipping_phone', ''),
                        buyer_name=request.user.get_full_name() or request.user.username,
                        redirect_url=request.data.get('redirect_url', ''),
                        cancel_url=request.data.get('cancel_url', ''),
                    )

                    if not result.success or not result.payment_url:
                        raise ValidationError(
                            f"Payment initiation failed: {result.error or 'unknown error'}. Order was not placed."
                        )

                    if isinstance(response_data, list):
                        response_data[0]['payment_url'] = result.payment_url
                        response_data[0]['transaction_reference'] = txn.reference
                    else:
                        response_data['payment_url'] = result.payment_url
                        response_data['transaction_reference'] = txn.reference

                return Response(response_data, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class OrderViewSet(viewsets.ModelViewSet):
    """
    API endpoint for orders.
    Buyers can view their orders, Sellers can view and update orders they receive.
    Admins can view and update all orders.
    """
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']  # POST retained for @action routes only; create() blocks POST /orders/

    # Selcom webhook has been moved to escrow_engine.views.SelcomWebhookView

    def get_queryset(self):
        """
        Strict filtering: Users can ONLY see orders where they are the buyer OR seller.
        Sellers can ONLY see orders where they are the seller (when role=seller).
        Buyers can ONLY see orders where they are the buyer (default).
        """
        if getattr(self, 'swagger_fake_view', False):
            return Order.objects.none()
        user = self.request.user
        role = self.request.query_params.get('role')
        
        if (user.is_superuser or user.is_staff) and role not in ['seller', 'buyer']:
            # Admins can see all orders UNLESS they specifically request a buyer or seller view
            qs = Order.objects.all()
        else:
            # Enforce STRICT filtering based on role
            role = role or 'buyer' # default to buyer if not provided
            
            # Check if user is a seller
            is_seller = Listing.objects.filter(owner=user).exists() or \
                       user.groups.filter(name__in=['seller', 'agent']).exists() or \
                       hasattr(user, 'seller_profile')
            
            if role == 'seller' and is_seller:
                # Seller viewing their orders - ONLY orders where they are the seller
                qs = Order.objects.filter(seller=user)
            else:
                # Buyer viewing their orders - ONLY orders where they are the buyer
                qs = Order.objects.filter(buyer=user)

        # By default, hide orders where payment was not even initiated (engine txn still CREATED).
        # Keep PENDING_PAYMENT visible so buyers/sellers can see the order while payment is in progress
        # (and potentially retry/continue payment). Staff can opt-in to include everything via
        # `?include_unpaid=1`.
        include_unpaid = str(self.request.query_params.get('include_unpaid', '')).strip() in ('1', 'true', 'yes')
        if not include_unpaid and not (user.is_superuser or user.is_staff):
            qs = qs.exclude(engine_transaction__status__in=[_TS.CREATED])

        return qs.prefetch_related(
            'items__listing__media',
            'evidence',
        ).select_related(
            'buyer__profile',
            'seller__profile',
            'seller__seller_profile',
            'engine_transaction',
        )

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed('POST', detail='Order creation is only allowed via cart checkout.')

    def get_object(self):
        """
        Override get_object to ensure users can ONLY access orders they're authorized to see.
        This prevents direct ID access to unauthorized orders.
        """
        user = self.request.user
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs[lookup_url_kwarg]
        
        # Try to get the order directly first (bypass queryset filtering for permission check)
        try:
            obj = Order.objects.select_related('buyer', 'seller').get(pk=lookup_value)
        except Order.DoesNotExist:
            raise NotFound("No Order matches the given query.")
        
        # Admins can access any order
        if user.is_superuser or user.is_staff:
            return obj
        
        # Non-admins can ONLY access orders where they are the buyer OR seller
        if obj.buyer != user and obj.seller != user:
            raise PermissionDenied("You do not have permission to access this order.")
        
        return obj

    def retrieve(self, request, *args, **kwargs):
        """
        Retrieve a single order with strict permission checking.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def list(self, request, *args, **kwargs):
        """
        List orders with strict filtering.
        """
        queryset = self.get_queryset()
        
        # Status filtering
        status_filter = request.query_params.get('status')
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        
        # Use pagination if available
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'count': queryset.count()
        })

    def partial_update(self, request, *args, **kwargs):
        """Allow sellers to update order status, tracking, and notes. Allow buyers to cancel orders."""
        order = self.get_object()
        user = request.user
        
        # Prevent any updates to cancelled orders
        if order.status == 'cancelled':
            return Response({'error': 'Cannot update a cancelled order'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if this is a cancellation request - buyers can cancel their orders
        is_cancellation = 'status' in request.data and request.data['status'] == 'cancelled'
        is_buyer = order.buyer == user
        
        # Handle order cancellation first - buyers can cancel their orders
        if is_cancellation:
            if not is_buyer:
                return Response({'error': 'Only the buyer can cancel an order'}, status=status.HTTP_403_FORBIDDEN)
            if order.status in ['shipped', 'arrived', 'delivered', 'disputed', 'completed']:
                return Response(
                    {
                        'error': (
                            'This order can no longer be cancelled because it has been shipped, arrived, or is finished. '
                            'Contact support if you need help.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Use OrderLifecycleManager to properly cancel order and sync escrow
            try:
                OrderLifecycleManager.cancel_order(order, actor=user)
                order.refresh_from_db()
                serializer = self.get_serializer(order)
                return Response({'success': True, 'order': serializer.data})
            except ValueError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        # For non-cancellation updates, check permissions (sellers and admins only)
        is_seller = order.seller == user
        is_admin = user.is_superuser or user.is_staff
        
        if not (is_seller or is_admin):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        # Source of Truth: order status changes only via OrderLifecycleManager / dedicated @actions.
        allowed_seller_fields = ['tracking_number', 'seller_notes', 'shipping_method', 'arrival_location']
        allowed_admin_fields = allowed_seller_fields + ['admin_notes', 'buyer_notes']

        if 'status' in request.data:
            return Response(
                {
                    'error': (
                        'Direct status updates are not allowed on this endpoint. '
                        'Use ship_order, confirm_receipt, or other order actions, '
                        'or cancel via status=cancelled (buyer only).'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        update_data = {}
        allowed = allowed_admin_fields if is_admin else allowed_seller_fields

        for field in allowed:
            if field in request.data:
                update_data[field] = request.data[field]

        for field, value in update_data.items():
            setattr(order, field, value)

        order.save()
        
        order.refresh_from_db()
        serializer = self.get_serializer(order)
        
        return Response({'success': True, 'order': serializer.data})

    @action(detail=True, methods=['post'])
    def ship_order(self, request, pk=None):
        """Allows the seller to mark an order as shipped and upload evidence."""
        order = self.get_object()
        user = request.user
        logger.info(f"Shipping order {order.id}. Current status: {order.status}. User: {user.username}. Request data keys: {request.data.keys()}. Files: {request.FILES.keys()}")
        
        if order.seller != user and not (user.is_superuser or user.is_staff):
            logger.warning(f"Permission denied for user {user.username} to ship order {order.id}")
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            
        if order.status not in ['pending', 'confirmed', 'processing']:
            logger.warning(f"Invalid status for shipping: {order.status}")
            return Response({'error': f'Cannot ship order in {order.status} status.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            OrderLifecycleManager.ship_order(
                order,
                tracking_number=request.data.get('tracking_number', ''),
                carrier=request.data.get('carrier', '') or request.data.get('shipping_method', ''),
                shipment_video=request.FILES.get('shipment_video'),
                shipment_images=request.FILES.getlist('shipment_images'),
                actor=user
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
        serializer = self.get_serializer(order)
        return Response({'success': True, 'order': serializer.data})

    @action(detail=True, methods=['post'])
    def mark_arrived(self, request, pk=None):
        """Allows the seller to mark an order as arrived at the destination."""
        order = self.get_object()
        user = request.user
        
        if order.seller != user and not (user.is_superuser or user.is_staff):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            
        if order.status != 'shipped':
            return Response({'error': f'Cannot mark order as arrived from {order.status} status.'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            OrderLifecycleManager.mark_arrived(order, actor=user)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            
        serializer = self.get_serializer(order)
        return Response({'success': True, 'order': serializer.data})

    @action(
        detail=True,
        methods=['post'],
        throttle_classes=[CommerceDisputeThrottle],
    )
    def open_dispute(self, request, pk=None):
        """Allows ONLY the buyer to open a dispute on an order."""
        order = self.get_object()
        user = request.user
        
        if order.buyer != user:
            return Response({'error': 'Only the buyer can open a dispute for this order.'}, status=status.HTTP_403_FORBIDDEN)
        
        # Disputes only after the package is marked arrived; not while in transit (shipped).
        if order.status in ['cancelled', 'completed', 'disputed', 'delivered']:
            return Response(
                {'error': f'Cannot open dispute for order in {order.status} status.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if order.status != 'arrived':
            return Response(
                {
                    'error': (
                        'Disputes can only be opened after the order is marked as arrived at your location. '
                        f'Current status: {order.status}.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        dispute_reason = request.data.get('dispute_reason', '').strip()
        if not dispute_reason:
            return Response({'error': 'Dispute reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_commerce_upload_files(
                video=request.FILES.get('evidence_video'),
                images=request.FILES.getlist('evidence_images'),
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        
        # Centralized Dispute Opening
        try:
            OrderLifecycleManager.open_dispute(order, actor=user, reason=dispute_reason)
            order.refresh_from_db()
            
            # Handle additional evidence files for the engine dispute
            eng_txn = EngTxn.objects.filter(linked_order=order).first()
            if eng_txn and eng_txn.dispute:
                eng_dispute = eng_txn.dispute
                # Evidence files (already validated in view)
                evidence_video = request.FILES.get('evidence_video')
                if evidence_video:
                    eng_dispute.evidence_video = evidence_video
                evidence_images = request.FILES.getlist('evidence_images')
                for img in evidence_images:
                    EngDisputeEvidence.objects.create(
                        dispute=eng_dispute, file=img, media_type='image', submitted_by=user
                    )
                if evidence_images or evidence_video:
                    eng_dispute.save()
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.error("Engine dispute opening failed for order %s: %s", order.id, exc)
            return Response({'error': f'Failed to open dispute: {str(exc)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        order.refresh_from_db()
        serializer = self.get_serializer(order)
        return Response({'success': True, 'order': serializer.data})
    
    @action(detail=True, methods=['post'])
    def resolve_dispute(self, request, pk=None):
        """Allows ONLY admins to resolve a dispute."""
        order = self.get_object()
        user = request.user
        
        if not (user.is_superuser or user.is_staff):
            return Response({'error': 'Only administrators can resolve disputes.'}, status=status.HTTP_403_FORBIDDEN)
        
        if order.status != 'disputed':
            return Response({'error': 'This order is not in disputed status.'}, status=status.HTTP_400_BAD_REQUEST)
        resolution = request.data.get('resolution', '').strip()  # 'refund' or 'release'
        admin_notes = request.data.get('admin_notes', '').strip()
        
        if resolution not in ['refund', 'release']:
            return Response({'error': 'Resolution must be either "refund" or "release".'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            OrderLifecycleManager.resolve_dispute(
                order, resolution=resolution, actor=user, admin_notes=admin_notes
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.warning("Engine dispute resolution error for order %s: %s", order.id, exc)
            return Response({'error': f'Failed to resolve dispute: {str(exc)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        order.refresh_from_db()
        serializer = self.get_serializer(order)
        return Response({'success': True, 'order': serializer.data})
    
    @action(detail=True, methods=['post'])
    def confirm_receipt(self, request, pk=None):
        """Allows ONLY the buyer to confirm they have received the order."""
        order = self.get_object()
        user = request.user
        
        if order.buyer != user:
            return Response({'error': 'Only the buyer can confirm receipt of this order.'}, status=status.HTTP_403_FORBIDDEN)
            
        if order.status not in ['shipped', 'arrived']:
            return Response(
                {'error': f'Cannot confirm receipt for order in {order.status} status. Order must be shipped or arrived.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        # Centralized receipt confirmation
        try:
            OrderLifecycleManager.confirm_receipt(order, actor=user)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.warning("Engine escrow release failed for order %s: %s", order.id, exc)
            return Response({'error': f'Failed to confirm receipt: {str(exc)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        order.refresh_from_db()
        serializer = self.get_serializer(order)
            
        return Response({'success': True, 'order': serializer.data})

    @action(
        detail=True,
        methods=['post'],
        url_path='initiate-payment',
        throttle_classes=[CommercePaymentInitiateThrottle],
    )
    def initiate_order_payment(self, request, pk=None):
        """
        Buyer: open hosted checkout for this order's escrow transaction
        (new payment or retry while status is CREATED / PENDING_PAYMENT).
        """
        order = self.get_object()
        user = request.user

        if order.buyer != user:
            return Response(
                {'error': 'Only the buyer can pay for this order.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        eng_txn = EngTxn.objects.filter(linked_order=order).first()
        if not eng_txn:
            return Response(
                {'error': 'No escrow transaction is linked to this order.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if eng_txn.status not in (_TS.CREATED, _TS.PENDING_PAYMENT):
            return Response(
                {
                    'error': (
                        f'Online checkout is not available for this payment '
                        f'(status {eng_txn.status}).'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_method = request.data.get('payment_method', 'mobile_money')
        payment_channel = request.data.get('payment_channel', payment_method)
        if not should_open_payment_gateway(payment_method):
            return Response(
                {'error': 'This payment method does not use online checkout.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        phone = (
            request.data.get('buyer_phone', '')
            or request.data.get('shipping_phone', '')
            or eng_txn.buyer_phone
            or ''
        )
        # Source of Truth: escrow_engine owns Transaction row updates (contact only, not status).
        eng_txn = sync_buyer_contact_for_checkout(
            eng_txn,
            buyer_email=user.email or '',
            buyer_phone=phone,
        )

        result = initiate_payment(
            eng_txn,
            actor=user,
            payment_method=payment_method,
            payment_channel=payment_channel,
            buyer_phone=phone,
            buyer_name=user.get_full_name() or user.username,
            redirect_url=request.data.get('redirect_url', ''),
            cancel_url=request.data.get('cancel_url', ''),
        )

        return Response(
            {
                'success': result.success,
                'payment_url': result.payment_url,
                'gateway_reference': result.gateway_reference,
                'transaction_reference': eng_txn.reference,
                'error': result.error,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=['post'],
        url_path='confirm-payment-return',
        throttle_classes=[CommercePaymentReturnThrottle],
    )
    def confirm_payment_return(self, request):
        """
        Refresh engine/order state after hosted checkout redirect.

        Source of Truth: payment confirmation runs in escrow_engine via
        confirm_marketplace_payment_return (verify + confirm_payment); this action is HTTP only.

        Never trusts client-reported payment status — verification is server-to-server
        via the configured payment provider (or idempotent engine state if already settled).
        """
        txn_ref = str(
            request.data.get('transaction_reference') or request.data.get('ref') or ''
        ).strip()

        try:
            txn = confirm_marketplace_payment_return(
                user=request.user,
                transaction_reference=txn_ref,
                raw_request_meta=dict(request.data),
            )
        except PermissionDenied as exc:
            return Response({'error': str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as exc:
            detail = exc.detail
            if isinstance(detail, dict):
                err = next(iter(detail.values()), detail)
                msg = err[0] if isinstance(err, list) else str(err)
            else:
                msg = str(detail)
            code = (
                status.HTTP_404_NOT_FOUND
                if 'not found' in msg.lower()
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({'error': msg}, status=code)
        except Exception as exc:
            logger.exception("Payment return confirmation failed for %s", txn_ref)
            return Response(
                {'error': f'Failed to confirm payment: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {'success': True, 'transaction': EngTxnSerializer(txn).data},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        order = self.get_object()
        user = request.user
        try:
            rating = request.data.get('rating')
            comment = request.data.get('comment', '')
            review_data = create_order_review(order, user, rating, comment)
            return Response(review_data, status=status.HTTP_201_CREATED)
        except PermissionDenied as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Failed to create order review: {e}")
            return Response({'error': 'An unexpected error occurred during review creation.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def seller_stats(self, request):
        """Returns stats specifically for seller's orders and finances."""
        user = request.user
        if not (user.is_superuser or user.groups.filter(name__in=['seller', 'agent']).exists() or
                Listing.objects.filter(owner=user).exists()):
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        stats_data = get_seller_stats(user)
        return Response(stats_data)

    @action(detail=False, methods=['get'])
    def seller_escrow(self, request):
        """Returns engine transactions (escrow) for the seller."""
        user = request.user
        escrow_qs = EngTxn.objects.filter(
            seller_user=user
        ).select_related('linked_order', 'buyer_user').order_by('-created_at')

        data = [{
            'id': str(e.id),
            'reference': e.reference,
            'order_id': str(e.linked_order_id) if e.linked_order_id else None,
            'amount': float(e.amount),
            'currency': e.currency,
            'status': e.status,
            'payment_method': e.payment_method,
            'payment_reference': e.gateway_reference,
            'held_at': e.held_at.isoformat() if e.held_at else None,
            'released_at': e.released_at.isoformat() if e.released_at else None,
            'buyer_name': e.buyer_display,
        } for e in escrow_qs[:50]]

        return Response({'escrow_transactions': data, 'count': len(data)})

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated, IsAdminUser],
    )
    def process(self, request, pk=None):
        """Process a pending engine payout for this order's escrow transaction (admin only)."""
        order = self.get_object()
        eng_txn = EngTxn.objects.filter(linked_order=order).first()
        if not eng_txn:
            return Response(
                {'error': 'No escrow transaction is linked to this order.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payout = EngPayout.objects.filter(transaction=eng_txn).first()
        if not payout:
            return Response(
                {'error': 'No payout record exists for this order yet (escrow may not be released).'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            process_seller_payout(payout)
            from commerce.services.audit import write_order_audit

            write_order_audit(
                order,
                'payout_process',
                actor=request.user,
                metadata={'payout_id': payout.pk},
            )
            payout.refresh_from_db()
            return Response(PayoutSerializer(payout).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Failed to process payout: {e}")
            try:
                from core.events import emit_event

                emit_event(
                    'PAYOUT_PROCESSING_FAILED',
                    {
                        'order_id': order.pk,
                        'payout_id': payout.pk,
                        'error': str(e)[:2000],
                    },
                    source_module='commerce.views.OrderViewSet.process',
                )
            except Exception:
                logger.debug('emit PAYOUT_PROCESSING_FAILED skipped', exc_info=True)
            return Response({'error': 'Failed to process payout.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def payouts(self, request):
        """Returns payout history. Sellers see their own; Admins see all (with optional status filtering)."""
        user = request.user
        role = request.query_params.get('role')
        status_filter = request.query_params.get('status')
        
        is_admin = user.is_superuser or user.is_staff
        
        if is_admin and role != 'seller':
            payout_qs = EngPayout.objects.all().order_by('-created_at')
        else:
            payout_qs = EngPayout.objects.filter(seller=user).order_by('-created_at')
            
        if status_filter and status_filter != 'all':
            payout_qs = payout_qs.filter(status=status_filter)
        
        # Use pagination for large payout lists
        page = self.paginate_queryset(payout_qs)
        
        # Calculate overall stats for summary cards (ignoring the current status filter but respecting the seller/admin context)
        # Using a separate base queryset for stats
        if is_admin and role != 'seller':
            stats_qs = EngPayout.objects.all()
        else:
            stats_qs = EngPayout.objects.filter(seller=user)

        summary_stats = {
            'pending': {'count': stats_qs.filter(status='pending').count(), 'amount': float(stats_qs.filter(status='pending').aggregate(Sum('amount'))['amount__sum'] or 0)},
            'processing': {'count': stats_qs.filter(status='processing').count(), 'amount': float(stats_qs.filter(status='processing').aggregate(Sum('amount'))['amount__sum'] or 0)},
            'released': {'count': stats_qs.filter(status='completed').count(), 'amount': float(stats_qs.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0)},
            'failed': {'count': stats_qs.filter(status='failed').count(), 'amount': float(stats_qs.filter(status='failed').aggregate(Sum('amount'))['amount__sum'] or 0)},
            'total_fees': 0 # Payout model does not store fees directly
        }

        if page is not None:
            serializer = PayoutSerializer(page, many=True)
            res = self.get_paginated_response(serializer.data)
            res.data['summary_stats'] = summary_stats
            return res

        serializer = PayoutSerializer(payout_qs, many=True)
        return Response({
            'results': serializer.data, 
            'count': payout_qs.count(),
            'summary_stats': summary_stats
        })

    @action(
        detail=False,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated, IsAdminUser],
    )
    def process_payout(self, request):
        """Process a specific payout by its ID (Admin only)."""
        payout_id = request.data.get('payout_id')
        if not payout_id:
            return Response({'error': 'payout_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        payout = get_object_or_404(EngPayout, pk=payout_id)
        
        try:
            process_seller_payout(payout)
            return Response(PayoutSerializer(payout).data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Failed to process payout {payout_id}: {e}")
            return Response({'error': 'Failed to process payout.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class WishlistViewSet(viewsets.ViewSet):
    """
    API endpoint for user's wishlist (saved items).
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WishlistSerializer

    def list(self, request):
        """Get all wishlisted items for the authenticated user."""
        wishlist, created = Wishlist.objects.get_or_create(user=request.user)
        serializer = WishlistSerializer(wishlist)
        return Response({
            'id': serializer.data['id'],
            'items': serializer.data['items'],
            'total_count': serializer.data['total_count'],
            'favorites': serializer.data['items']  # Also include as 'favorites' for compatibility
        })
    
    @action(detail=False, methods=['post'])
    def add(self, request):
        """Add a listing to the user's wishlist."""
        listing_id = request.data.get('listing_id')
        if not listing_id:
            return Response(
                {'error': 'listing_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create user's wishlist
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        
        # Check if listing exists
        listing = get_object_or_404(Listing, id=listing_id)
        
        # Add to wishlist (or skip if already exists)
        wishlist_item, created = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            listing=listing
        )
        
        if created:
            logger.info(f"Added listing {listing_id} to wishlist for user {request.user.id}")
        
        serializer = WishlistItemSerializer(wishlist_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def remove(self, request):
        """Remove a listing from the user's wishlist."""
        wishlist_item_id = request.data.get('wishlist_item_id') or request.data.get('item_id')
        if not wishlist_item_id:
            return Response(
                {'error': 'wishlist_item_id or item_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        wishlist_item = get_object_or_404(WishlistItem, id=wishlist_item_id, wishlist__user=request.user)
        wishlist_item.delete()
        
        logger.info(f"Removed item {wishlist_item_id} from wishlist for user {request.user.id}")
        
        return Response({'success': True, 'message': 'Item removed from wishlist'})
    
    @action(detail=False, methods=['post'])
    def toggle(self, request):
        """Toggle a listing in the user's wishlist (add if not present, remove if present)."""
        listing_id = request.data.get('listing_id')
        if not listing_id:
            return Response(
                {'error': 'listing_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create user's wishlist
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
        
        # Check if listing exists
        listing = get_object_or_404(Listing, id=listing_id)
        
        # Try to get existing wishlist item
        try:
            wishlist_item = WishlistItem.objects.get(wishlist=wishlist, listing=listing)
            # Item exists, remove it
            wishlist_item.delete()
            logger.info(f"Removed listing {listing_id} from wishlist for user {request.user.id}")
            return Response({'success': True, 'added': False, 'message': 'Item removed from wishlist'})
        except WishlistItem.DoesNotExist:
            # Item doesn't exist, add it
            wishlist_item = WishlistItem.objects.create(wishlist=wishlist, listing=listing)
            logger.info(f"Added listing {listing_id} to wishlist for user {request.user.id}")
            serializer = WishlistItemSerializer(wishlist_item)
            return Response({
                'success': True,
                'added': True,
                'message': 'Item added to wishlist',
                'item': serializer.data
            }, status=status.HTTP_201_CREATED)