"""
WebSocket consumers for real-time dashboard updates.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta

from commerce.models import Order
from escrow_engine.models import Transaction, Payout
from escrow_engine.state_machine import TransactionStatus as _TS
from listings.models import Listing
from marketplace.models import SellerProfile

logger = logging.getLogger(__name__)
User = get_user_model()


class DashboardConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time dashboard updates."""
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope["user"]
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        # Determine user role and set appropriate group
        role = await self.get_user_role()
        if role == 'admin':
            self.group_name = 'dashboard_admin'
        elif role == 'seller':
            self.group_name = f'dashboard_seller_{self.user.id}'
        else:
            self.group_name = f'dashboard_buyer_{self.user.id}'
        
        # Join appropriate group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial data
        await self.send_initial_data()
        
        logger.info(f"User {self.user.username} connected to dashboard WebSocket")
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        logger.info(f"User {self.user.username} disconnected from dashboard WebSocket")
    
    async def receive(self, text_data):
        """Handle incoming messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'refresh')
            
            if message_type == 'refresh':
                await self.send_initial_data()
            elif message_type == 'subscribe':
                # Subscribe to specific updates
                await self.handle_subscribe(data)
        except json.JSONDecodeError:
            logger.error("Invalid JSON received in dashboard WebSocket")
        except Exception as e:
            logger.error(f"Error in dashboard WebSocket receive: {e}")
    
    async def send_initial_data(self):
        """Send initial dashboard data."""
        role = await self.get_user_role()
        
        if role == 'admin':
            stats = await self.get_admin_stats()
            # Also send initial data for faster loading
            initial_data = await self.get_admin_initial_data()
            data = {**stats, **initial_data}
        elif role == 'seller':
            data = await self.get_seller_stats()
        else:
            data = await self.get_buyer_stats()
        
        await self.send(text_data=json.dumps({
            'type': 'dashboard_data',
            'data': data,
            'timestamp': timezone.now().isoformat()
        }))
    
    @database_sync_to_async
    def get_admin_initial_data(self):
        """Get initial admin dashboard data (orders, listings, users) for faster loading."""
        try:
            # Get limited recent data for initial load - just IDs and basic info
            # Full data will be loaded by frontend as needed
            recent_orders = Order.objects.select_related('buyer', 'seller')[:50]
            recent_listings = Listing.objects.select_related('owner', 'category')[:50]
            recent_users = User.objects.select_related('profile', 'seller_profile')[:50]
            
            # Return minimal data to speed up WebSocket response
            # Frontend will fetch full data via API if needed
            return {
                'orders_count': recent_orders.count(),
                'listings_count': recent_listings.count(),
                'users_count': recent_users.count(),
                # Send just IDs for faster initial load - frontend can fetch details on demand
                'recent_order_ids': [o.id for o in recent_orders[:10]],
                'recent_listing_ids': [l.id for l in recent_listings[:10]],
                'recent_user_ids': [u.id for u in recent_users[:10]],
            }
        except Exception as e:
            logger.error(f"Error getting admin initial data: {e}")
            return {}
    
    async def handle_subscribe(self, data):
        """Handle subscription to specific updates."""
        subscriptions = data.get('subscriptions', [])
        # Store subscriptions for future use
        self.subscriptions = subscriptions
    
    # Event handlers for broadcasting updates
    async def dashboard_update(self, event):
        """Send dashboard update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'dashboard_update',
            'data': event['data'],
            'update_type': event.get('update_type', 'general'),
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))
    
    async def order_update(self, event):
        """Send order update to WebSocket (minimal payload; refetch details via API if needed)."""
        await self.send(text_data=json.dumps({
            'type': 'order_update',
            'order_id': event.get('order_id'),
            'status': event.get('status'),
            'buyer_id': event.get('buyer_id'),
            'seller_id': event.get('seller_id'),
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))
    
    async def stats_update(self, event):
        """Send stats update to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'stats_update',
            'stats': event['stats'],
            'timestamp': event.get('timestamp', timezone.now().isoformat())
        }))
    
    # Database operations
    @database_sync_to_async
    def get_user_role(self):
        """Get user role."""
        if self.user.is_superuser:
            return 'admin'
        elif hasattr(self.user, 'seller_profile') and self.user.seller_profile.is_active:
            return 'seller'
        else:
            return 'buyer'
    
    @database_sync_to_async
    def get_admin_stats(self):
        """Get admin dashboard statistics with caching."""
        from django.core.cache import cache
        
        # Cache key
        cache_key = 'admin_stats_dashboard_ws'
        cache_timeout = 30  # Cache for 30 seconds (shorter than API cache)
        
        # Try to get from cache first
        cached_stats = cache.get(cache_key)
        if cached_stats:
            return cached_stats
        
        try:
            from django.db.models import Q
            
            # Optimize queries - use aggregate with filters
            order_stats = Order.objects.aggregate(
                total=Count('id'),
                pending=Count('id', filter=Q(status='pending')),
                completed=Count('id', filter=Q(status='completed')),
                cancelled=Count('id', filter=Q(status='cancelled')),
            )
            
            revenue_stats = Order.objects.filter(status='completed').aggregate(
                total=Sum('total_amount'),
                today=Sum('total_amount', filter=Q(completed_at__date=timezone.now().date()))
            )
            
            escrow_stats = Transaction.objects.aggregate(
                held=Sum('amount', filter=Q(status=_TS.HOLD)),
                released=Sum('amount', filter=Q(status=_TS.RELEASED))
            )
            
            listing_stats = Listing.objects.filter(is_published=True).aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(status='active'))
            )
            
            user_stats = {
                'total': User.objects.count(),
                'sellers': SellerProfile.objects.filter(is_active=True).count(),
            }
            
            stats = {
                'orders': {
                    'total': order_stats['total'] or 0,
                    'pending': order_stats['pending'] or 0,
                    'completed': order_stats['completed'] or 0,
                    'cancelled': order_stats['cancelled'] or 0,
                },
                'revenue': {
                    'total': float(revenue_stats['total'] or 0),
                    'today': float(revenue_stats['today'] or 0),
                },
                'escrow': {
                    'held': float(escrow_stats['held'] or 0),
                    'released': float(escrow_stats['released'] or 0),
                },
                'listings': {
                    'total': listing_stats['total'] or 0,
                    'active': listing_stats['active'] or 0,
                },
                'users': user_stats
            }
            
            # Cache the results
            cache.set(cache_key, stats, cache_timeout)
            
            return stats
        except Exception as e:
            logger.error(f"Error getting admin stats: {e}")
            return {}
    
    @database_sync_to_async
    def get_seller_stats(self):
        """Get seller dashboard statistics."""
        try:
            seller_profile = self.user.seller_profile
            
            orders = Order.objects.filter(seller=self.user)
            completed_orders = orders.filter(status='completed')
            
            stats = {
                'orders': {
                    'total': orders.count(),
                    'pending': orders.filter(status='pending').count(),
                    'completed': completed_orders.count(),
                },
                'revenue': {
                    'total': float(completed_orders.aggregate(
                        total=Sum('subtotal')
                    )['total'] or 0),
                    'net_earnings': float(completed_orders.aggregate(
                        net=Sum('subtotal') - Sum('platform_fee')
                    )['net'] or 0),
                },
                'listings': {
                    'total': Listing.objects.filter(owner=self.user).count(),
                    'active': Listing.objects.filter(
                        owner=self.user,
                        is_published=True,
                        status='active'
                    ).count(),
                },
                'escrow': {
                    'held': float(Transaction.objects.filter(
                        linked_order__seller=self.user,
                        status=_TS.HOLD
                    ).aggregate(total=Sum('amount'))['total'] or 0),
                },
                'payouts': {
                    'pending': float(Payout.objects.filter(
                        seller=self.user,
                        status__in=['pending', 'processing']
                    ).aggregate(total=Sum('amount'))['total'] or 0),
                }
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting seller stats: {e}")
            return {}
    
    @database_sync_to_async
    def get_buyer_stats(self):
        """Get buyer dashboard statistics."""
        try:
            orders = Order.objects.filter(buyer=self.user)
            
            stats = {
                'orders': {
                    'total': orders.count(),
                    'pending': orders.filter(status='pending').count(),
                    'completed': orders.filter(status='completed').count(),
                },
                'spending': {
                    'total': float(orders.filter(status='completed').aggregate(
                        total=Sum('total_amount')
                    )['total'] or 0),
                }
            }
            return stats
        except Exception as e:
            logger.error(f"Error getting buyer stats: {e}")
            return {}
