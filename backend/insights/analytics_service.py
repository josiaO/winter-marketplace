from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncDate, ExtractWeekDay
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth import get_user_model
from collections import defaultdict

from .models import (
    Event, ListingEngagement, SellerLeadMetrics, 
    GeographicInsight, WeeklyEngagementPattern, Visitor
)
from listings.models import Listing, ListingLike, ListingMedia, ListingView
from commerce.models import Order, OrderItem
from communications.models import Message, Conversation
from trust.models import Review
from escrow_engine.models import Transaction as EngTxn, Payout
from escrow_engine.state_machine import TransactionStatus as _TS
from marketplace.models import SellerProfile

User = get_user_model()

class AnalyticsService:
    """Service for aggregating analytics data for the admin dashboard."""
    
    @staticmethod
    def get_overview_stats(days=30):
        """Get high-level KPIs."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        previous_start = start_date - timedelta(days=days)
        
        # Calculate totals
        total_visitors = Event.objects.filter(
            event_type='page_view', 
            created_at__gte=start_date
        ).values('session_id').distinct().count()
        
        prev_visitors = Event.objects.filter(
            event_type='page_view', 
            created_at__range=(previous_start, start_date)
        ).values('session_id').distinct().count()
        
        total_leads = Event.objects.filter(
            event_type__in=['seller_contact', 'order_request'],
            created_at__gte=start_date
        ).count()
        
        prev_leads = Event.objects.filter(
            event_type__in=['seller_contact', 'order_request'],
            created_at__range=(previous_start, start_date)
        ).count()
        
        return {
            "visitors": {
                "value": total_visitors,
                "change": AnalyticsService._calculate_percentage_change(prev_visitors, total_visitors)
            },
            "leads": {
                "value": total_leads,
                "change": AnalyticsService._calculate_percentage_change(prev_leads, total_leads)
            },
            "listings_viewed": Event.objects.filter(
                event_type='listing_view',
                created_at__gte=start_date
            ).count(),
            "signups": User.objects.filter(
                date_joined__gte=start_date
            ).count()
        }
    
    @staticmethod
    def get_traffic_chart(days=30):
        """Get daily traffic stats for charting."""
        start_date = timezone.now() - timedelta(days=days)
        
        stats = Event.objects.filter(
            event_type='page_view',
            created_at__gte=start_date
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            visitors=Count('session_id', distinct=True),
            page_views=Count('id')
        ).order_by('date')
        
        return list(stats)

    
    @staticmethod
    def get_device_stats(days=30):
        """Get device breakdown."""
        start_date = timezone.now() - timedelta(days=days)
        
        return Event.objects.filter(
            event_type='page_view',
            created_at__gte=start_date
        ).values('device_type').annotate(
            count=Count('id')
        ).order_by('-count')
    
    @staticmethod
    def get_top_performing_listings(days=30, limit=5):
        """Get most viewed/contacted listings."""
        # Using Listing's internal view_count
        return Listing.objects.filter(is_published=True).order_by('-view_count')[:limit].values(
            'id', 'title', 'price', 'view_count'
        )

    @staticmethod
    def _calculate_percentage_change(old_value, new_value):
        if old_value == 0:
            return 100 if new_value > 0 else 0
        return ((new_value - old_value) / old_value) * 100

    @staticmethod
    def get_admin_dashboard_stats():
        """Aggregates platform-wide KPIs for the admin dashboard."""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        user_stats = User.objects.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(is_active=True)),
            new_today=Count('id', filter=Q(date_joined__gte=today_start)),
            new_this_month=Count('id', filter=Q(date_joined__gte=thirty_days_ago))
        )
        
        total_sellers = SellerProfile.objects.filter(is_active=True).count()
        
        listing_stats = Listing.objects.aggregate(
            total=Count('id'),
            published=Count('id', filter=Q(is_published=True))
        )
        
        order_stats = Order.objects.aggregate(
            total=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            completed=Count('id', filter=Q(status__in=['completed', 'delivered'])),
            cancelled=Count('id', filter=Q(status='cancelled')),
            revenue=Sum('total_amount', filter=Q(status__in=['completed', 'delivered'])),
            fees=Sum('platform_fee', filter=Q(status__in=['completed', 'delivered']))
        )
        
        escrow_totals = EngTxn.objects.aggregate(
            held=Sum('amount', filter=Q(status=_TS.HOLD)),
            released=Sum('amount', filter=Q(status=_TS.RELEASED)),
            refunded=Sum('amount', filter=Q(status=_TS.REFUNDED)),
            disputed=Sum('amount', filter=Q(status=_TS.DISPUTED))
        )
        
        return {
            'total_users': user_stats['total'],
            'active_users': user_stats['active'],
            'new_users_today': user_stats['new_today'],
            'new_users_this_month': user_stats['new_this_month'],
            'total_sellers': total_sellers,
            'marketplace_listings': listing_stats['published'] or 0,
            'total_listings': listing_stats['total'] or 0,
            'total_orders': order_stats['total'] or 0,
            'pending_orders': order_stats['pending'] or 0,
            'completed_orders': order_stats['completed'] or 0,
            'cancelled_orders': order_stats['cancelled'] or 0,
            'total_revenue': float(order_stats['revenue'] or 0),
            'platform_fees': float(order_stats['fees'] or 0),
            'escrow': {
                'held': float(escrow_totals['held'] or 0),
                'released': float(escrow_totals['released'] or 0),
                'refunded': float(escrow_totals['refunded'] or 0),
                'disputed': float(escrow_totals['disputed'] or 0),
            }
        }

    @staticmethod
    def get_platform_metrics():
        """Aggregates high-level platform performance metrics for Analytics view."""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # 1. GMV and Commissions
        order_metrics = Order.objects.filter(status__in=['completed', 'delivered']).aggregate(
            gmv=Sum('total_amount'),
            commission=Sum('platform_fee')
        )
        
        # 2. Escrow Status
        escrow_metrics = EngTxn.objects.aggregate(
            held=Sum('amount', filter=Q(status=_TS.HOLD)),
            released=Sum('amount', filter=Q(status=_TS.RELEASED))
        )
        
        # 3. Active Users (Last 30 days)
        # Using date_joined or last_login as proxy, or Visitors
        active_users_30d = User.objects.filter(
            Q(last_login__gte=thirty_days_ago) | Q(date_joined__gte=thirty_days_ago)
        ).count()
        
        # 4. Conversion Rate (Orders / Unique Visitors)
        total_visitors = Visitor.objects.filter(last_seen__gte=thirty_days_ago).count()
        total_orders_30d = Order.objects.filter(created_at__gte=thirty_days_ago).count()
        conversion_rate = (total_orders_30d / total_visitors * 100) if total_visitors > 0 else 0
        
        # 5. Avg Order Value
        avg_order_value = Order.objects.filter(status__in=['completed', 'delivered']).aggregate(
            avg=Avg('total_amount')
        )['avg'] or 0
        
        # 6. Top Categories
        from marketplace.models import Category
        top_categories = Listing.objects.values('category__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # 7. Top Sellers
        top_sellers = Order.objects.filter(status__in=['completed', 'delivered']).values(
            'seller__username', 'seller__first_name', 'seller__last_name'
        ).annotate(
            revenue=Sum('total_amount'),
            orders=Count('id')
        ).order_by('-revenue')[:10]
        
        return {
            'total_gmv': float(order_metrics['gmv'] or 0),
            'total_commission': float(order_metrics['commission'] or 0),
            'total_escrow_held': float(escrow_metrics['held'] or 0),
            'total_payouts_released': float(escrow_metrics['released'] or 0),
            'active_users_30d': active_users_30d,
            'conversion_rate': round(float(conversion_rate), 2),
            'avg_order_value': float(avg_order_value),
            'top_categories': [
                {'category': item['category__name'] or 'Uncategorized', 'count': item['count']}
                for item in top_categories
            ],
            'top_sellers': [
                {
                    'seller': f"{item['seller__first_name']} {item['seller__last_name']}".strip() or item['seller__username'],
                    'revenue': float(item['revenue'] or 0), 
                    'orders': item['orders']
                }
                for item in top_sellers
            ]
        }

    @staticmethod
    def get_public_stats_summary():
        """Curated public stats for homepage social proof."""
        raw_listings = Listing.objects.filter(is_published=True, deleted_at__isnull=True).count()
        raw_sellers = SellerProfile.objects.filter(is_active=True).count()
        total_visitors = Visitor.objects.count()
        
        # Formatting logic (e.g. "2.5k+")
        def format_count(count):
            if count > 1000: return f"{count/1000:,.1f}k+"
            if count > 100: return f"{(count//10)*10}+"
            return f"{count}+" if count > 10 else str(count)

        return {
            "listings": format_count(raw_listings),
            "sellers": format_count(raw_sellers),
            "visitors": format_count(total_visitors),
            "satisfaction": "96%", # Curated metric
            "raw": {
                "listings": raw_listings,
                "sellers": raw_sellers,
                "visitors": total_visitors
            }
        }

    @staticmethod
    def get_growth_metrics(metric_type='users', days=365):
        """Generic growth metric aggregator by month."""
        from django.db.models.functions import TruncMonth
        start_date = timezone.now() - timedelta(days=days)
        
        if metric_type == 'users':
            qs = User.objects.filter(date_joined__gte=start_date).annotate(month=TruncMonth('date_joined'))
            result = qs.values('month').annotate(count=Count('id')).order_by('month')
            key = 'users'
        elif metric_type == 'listings':
            qs = Listing.objects.filter(created_at__gte=start_date).annotate(month=TruncMonth('created_at'))
            result = qs.values('month').annotate(count=Count('id')).order_by('month')
            key = 'listings'
        elif metric_type == 'revenue':
            qs = Order.objects.filter(status__in=['completed', 'delivered'], created_at__gte=start_date).annotate(month=TruncMonth('created_at'))
            result = qs.values('month').annotate(count=Sum('total_amount')).order_by('month')
            key = 'revenue'
        elif metric_type == 'orders':
            qs = Order.objects.filter(created_at__gte=start_date).annotate(month=TruncMonth('created_at'))
            result = qs.values('month').annotate(count=Count('id')).order_by('month')
            key = 'orders'
        else:
            return []

        return [
            {'month': item['month'].strftime('%b %Y'), key: float(item['count'])}
            for item in result if item['month']
        ]

    @staticmethod
    def get_buyer_stats(user):
        """Get dashboard statistics for a buyer."""
        orders = Order.objects.filter(buyer=user)
        total_spent = orders.filter(status='completed').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        first_day_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        return {
            'orders': {
                'total': orders.count(),
                'active': orders.filter(status__in=['pending', 'confirmed', 'processing', 'shipped', 'arrived']).count(),
                'completed': orders.filter(status='completed').count(),
                'this_month': orders.filter(created_at__gte=first_day_of_month).count(),
            },
            'spent': float(total_spent),
            'favorites': ListingLike.objects.filter(user=user).count(),
            'reviews': Review.objects.filter(buyer=user).count()
        }


class SellerAnalyticsService:
    """
    Service for calculating seller dashboard analytics.
    Unified marketplace version.
    """
    
    def __init__(self, seller_id):
        self.seller_id = seller_id
        try:
            self.seller = User.objects.get(id=seller_id)
        except User.DoesNotExist:
            raise ValueError(f"Seller with id {seller_id} not found")
    
    def get_listing_overview(self, days=30):
        """Get overview metrics for seller's listings."""
        seller_listings = Listing.objects.filter(owner=self.seller)
        
        end_date = timezone.now()
        start_date_7d = end_date - timedelta(days=7)
        start_date_30d = end_date - timedelta(days=30)
        
        total_listings = seller_listings.count()
        active_listings = seller_listings.filter(is_published=True, deleted_at__isnull=True).count()
        inactive_listings = total_listings - active_listings
        
        total_views = seller_listings.aggregate(total=Sum('view_count'))['total'] or 0
        
        views_7d = ListingView.objects.filter(
            listing__owner=self.seller,
            viewed_at__gte=start_date_7d
        ).count()
        
        views_30d = ListingView.objects.filter(
            listing__owner=self.seller,
            viewed_at__gte=start_date_30d
        ).count()
        
        # Using orders as proxy for inquiries for now
        total_inquiries = Order.objects.filter(seller=self.seller).count()
        
        inquiries_7d = Order.objects.filter(
            seller=self.seller,
            created_at__gte=start_date_7d
        ).count()
        
        inquiries_30d = Order.objects.filter(
            seller=self.seller,
            created_at__gte=start_date_30d
        ).count()
        
        return {
            'total_listings': total_listings,
            'active_listings': active_listings,
            'inactive_listings': inactive_listings,
            'total_views': total_views,
            'views_7d': views_7d,
            'views_30d': views_30d,
            'total_inquiries': total_inquiries,
            'inquiries_7d': inquiries_7d,
            'inquiries_30d': inquiries_30d,
        }
    
    def get_listing_performance(self, listing_id=None, days=30):
        """Get detailed performance metrics for listings."""
        seller_listings = Listing.objects.filter(owner=self.seller, deleted_at__isnull=True)
        
        if listing_id:
            seller_listings = seller_listings.filter(id=listing_id)
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        performance_data = []
        
        for listing in seller_listings:
            views_by_day = ListingView.objects.filter(
                listing=listing,
                viewed_at__gte=start_date
            ).annotate(
                day=TruncDate('viewed_at')
            ).values('day').annotate(
                count=Count('id')
            ).order_by('day')
            
            views_over_time = [
                {'date': item['day'].isoformat() if item['day'] else '', 'views': item['count']}
                for item in views_by_day
                if item['day']
            ]
            
            # ListingView doesn't have device_type yet, using a dummy for now or skipping
            device_data = {'mobile': 0, 'desktop': 0, 'tablet': 0}
            
            engagement = ListingEngagement.objects.filter(listing=listing).first()
            likes_count = ListingLike.objects.filter(listing=listing).count()
            contact_attempts = Order.objects.filter(listing=listing).count() # Or from Message/Conversation
            
            top_days = ListingView.objects.filter(
                listing=listing,
                viewed_at__gte=start_date
            ).annotate(
                day_num=ExtractWeekDay('viewed_at')
            ).values('day_num').annotate(
                count=Count('id')
            ).order_by('-count')[:3]
            
            day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            top_traffic_days = [day_names[item['day_num'] - 1] for item in top_days if item['day_num']]
            
            performance_data.append({
                'listing_id': listing.id,
                'title': listing.title,
                'views_over_time': views_over_time,
                'total_views': listing.view_count,
                'likes': likes_count,
                'shares': engagement.total_shares if engagement else 0,
                'contact_attempts': contact_attempts,
                'top_traffic_days': top_traffic_days,
                'device_breakdown': device_data
            })
        
        return performance_data
    
    def get_lead_insights(self, days=30):
        """Get lead and buyer behavior analytics."""
        end_date = timezone.now()
        start_date_7d = end_date - timedelta(days=7)
        start_date_30d = end_date - timedelta(days=30)
        
        seller_conversations = Conversation.objects.filter(seller=self.seller)
        
        new_messages_7d = Message.objects.filter(
            conversation__seller=self.seller,
            created_at__gte=start_date_7d
        ).exclude(sender=self.seller).count()
        
        new_messages_30d = Message.objects.filter(
            conversation__seller=self.seller,
            created_at__gte=start_date_30d
        ).exclude(sender=self.seller).count()
        
        conversations_started = seller_conversations.filter(
            created_at__gte=start_date_30d
        ).count()
        
        relevant_messages = Message.objects.filter(
            conversation__in=seller_conversations,
            created_at__gte=start_date_30d
        ).select_related('conversation').order_by('conversation__id', 'created_at')
        
        total_response_time = 0
        response_count = 0
        
        msgs_by_conv = defaultdict(list)
        for msg in relevant_messages:
            msgs_by_conv[msg.conversation_id].append(msg)
            
        for conv_id, msgs in msgs_by_conv.items():
            last_user_msg_time = None
            
            for msg in msgs:
                if msg.sender_id != self.seller_id:
                    last_user_msg_time = msg.created_at
                elif msg.sender_id == self.seller_id:
                     if last_user_msg_time:
                         time_diff = msg.created_at - last_user_msg_time
                         total_response_time += time_diff.total_seconds()
                         response_count += 1
                         last_user_msg_time = None
        
        avg_response_time = total_response_time / response_count if response_count > 0 else 0
        avg_response_time_str = self._format_response_time(avg_response_time)
        
        most_ordered = Order.objects.filter(
            seller=self.seller
        ).values('listing__id', 'listing__title').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        return {
            'new_messages_7d': new_messages_7d,
            'new_messages_30d': new_messages_30d,
            'conversations_started': conversations_started,
            'avg_response_time': avg_response_time_str,
            'avg_response_time_seconds': int(avg_response_time),
            'most_ordered_listing': {
                'id': most_ordered['listing__id'],
                'title': most_ordered['listing__title'],
                'count': most_ordered['count']
            } if most_ordered else None
        }
    
    def get_geographic_insights(self, days=30):
        """Get location-based analytics."""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Simple stats from ListingView (doesn't have location_city yet)
        top_view_locations = ListingView.objects.filter(
            listing__owner=self.seller,
            viewed_at__gte=start_date,
        ).values('ip_address').annotate( # IP as proxy for location for now
            count=Count('id')
        ).order_by('-count')[:10]
        
        return {
            'top_view_locations': [
                {'location': item['ip_address'], 'count': item['count']}
                for item in top_view_locations
            ]
        }
    
    def get_engagement_heatmap(self):
        """Get weekly engagement pattern heatmap."""
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        
        patterns = WeeklyEngagementPattern.objects.filter(
            seller=self.seller,
            week_start_date=week_start
        ).order_by('day_of_week')
        
        if not patterns.exists():
            self._calculate_weekly_patterns(week_start)
            patterns = WeeklyEngagementPattern.objects.filter(
                seller=self.seller,
                week_start_date=week_start
            ).order_by('day_of_week')
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        heatmap_data = []
        
        for day in days:
            pattern = patterns.filter(day_of_week=day).first()
            heatmap_data.append({
                'day': day,
                'level': pattern.activity_level if pattern else 'Low'
            })
        
        return {'days': heatmap_data}
    
    def get_optimization_suggestions(self):
        """Generate optimization suggestions for seller's listings."""
        suggestions = []
        
        seller_listings = Listing.objects.filter(
            owner=self.seller, 
            is_published=True,
            deleted_at__isnull=True
        ).annotate(
            media_count=Count('media'),
            video_count=Count('media', filter=Q(media__media_type='video'))
        )
        
        for listing in seller_listings:
            media_count = listing.media_count
            
            if media_count == 0:
                suggestions.append({
                    'listing_id': listing.id,
                    'listing_title': listing.title,
                    'type': 'images',
                    'message': f'"{listing.title}" has no images. Listings with images get 5× more views.'
                })
            elif media_count == 1:
                suggestions.append({
                    'listing_id': listing.id,
                    'listing_title': listing.title,
                    'type': 'images',
                    'message': f'Add more images to "{listing.title}". Listings with 5+ images get 2× more inquiries.'
                })
            
            has_video = listing.video_count > 0
            
            if not has_video and media_count > 0:
                suggestions.append({
                    'listing_id': listing.id,
                    'listing_title': listing.title,
                    'type': 'video',
                    'message': f'Add a video to "{listing.title}". Listings with videos receive 40% more inquiries.'
                })
            
            if listing.view_count < 10:
                suggestions.append({
                    'listing_id': listing.id,
                    'listing_title': listing.title,
                    'type': 'visibility',
                    'message': f'"{listing.title}" has low visibility. Consider updating the description or price.'
                })
        
        return suggestions[:5]
    
    def get_quick_wins(self):
        """Get actionable quick-win items."""
        quick_wins = []
        
        listings_need_images = Listing.objects.filter(
            owner=self.seller,
            is_published=True,
            deleted_at__isnull=True
        ).annotate(
            media_count=Count('media')
        ).filter(media_count__lt=3)
        
        if listings_need_images.exists():
            quick_wins.append({
                'action': 'add_images',
                'title': f'Add more images to {listings_need_images.count()} listings',
                'count': listings_need_images.count(),
                'link': '/seller/my-listings'
            })
        
        pending_messages = Message.objects.filter(
            conversation__seller=self.seller,
            read_at__isnull=True
        ).exclude(sender=self.seller).count()
        
        if pending_messages > 0:
            quick_wins.append({
                'action': 'respond_messages',
                'title': f'Respond to {pending_messages} pending messages',
                'count': pending_messages,
                'link': '/communication'
            })
        
        return quick_wins

    def get_stats_summary(self):
        """Comprehensive stats summary for seller dashboard."""
        overview = self.get_listing_overview(days=30)
        
        # Financials
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        seller_orders = Order.objects.filter(seller=self.seller)
        revenue_today = seller_orders.filter(status__in=['completed', 'delivered'], created_at__gte=today_start).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        revenue_month = seller_orders.filter(status__in=['completed', 'delivered'], created_at__gte=month_start).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        total_revenue = seller_orders.filter(status__in=['completed', 'delivered']).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # Escrow
        escrow_held = EngTxn.objects.filter(linked_order__seller=self.seller, status=_TS.HOLD).aggregate(Sum('amount'))['amount__sum'] or 0
        escrow_released = EngTxn.objects.filter(linked_order__seller=self.seller, status=_TS.RELEASED).aggregate(Sum('amount'))['amount__sum'] or 0
        escrow_disputed = EngTxn.objects.filter(linked_order__seller=self.seller, status=_TS.DISPUTED).aggregate(Sum('amount'))['amount__sum'] or 0
        
        pending_payouts = Payout.objects.filter(seller=self.seller, status='pending').aggregate(Sum('amount'))['amount__sum'] or 0
        completed_payouts = Payout.objects.filter(seller=self.seller, status='completed').aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Formatting for response
        return {
            **overview,
            'earnings_today': float(revenue_today),
            'earnings_this_month': float(revenue_month),
            'total_earnings': float(total_revenue),
            'escrow': {
                'held': float(escrow_held),
                'released': float(escrow_released),
                'disputed': float(escrow_disputed),
            },
            'payouts': {
                'pending': float(pending_payouts),
                'completed': float(completed_payouts),
            },
            'order_status_breakdown': dict(seller_orders.values('status').annotate(count=Count('id')).values_list('status', 'count'))
        }

    def _format_response_time(self, seconds):
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''}"
    
    def _calculate_weekly_patterns(self, week_start):
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for i, day_name in enumerate(days_of_week):
            day_date = week_start + timedelta(days=i)
            next_day = day_date + timedelta(days=1)
            views = ListingView.objects.filter(
                listing__owner=self.seller,
                viewed_at__gte=day_date,
                viewed_at__lt=next_day
            ).count()
            orders = Order.objects.filter(
                seller=self.seller,
                created_at__gte=day_date,
                created_at__lt=next_day
            ).count()
            pattern, created = WeeklyEngagementPattern.objects.get_or_create(
                seller=self.seller,
                week_start_date=week_start,
                day_of_week=day_name,
                defaults={
                    'total_views': views,
                    'total_inquiries': orders
                }
            )
            if not created:
                pattern.total_views = views
                pattern.total_inquiries = orders
                pattern.save()
            pattern.calculate_activity_level()
