"""
Django Admin Configuration for SmartDalali

Centralized admin customization with modern dashboard statistics.
All model admins are registered in their respective app admin modules.
"""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum, Q

# Import models from all apps to ensure admin registration
from communications.models import Conversation, Message, Notification
from insights.models import Visitor
from catalog.models import Category, CategoryField
from listings.models import Listing
from commerce.models import Order, Cart

User = get_user_model()


# ============== Admin Site Customization ==============
admin.site.site_header = "DigitalDalali Administration"
admin.site.site_title = "DigitalDalali Admin"
admin.site.index_title = "Dashboard Overview"


# ============== Dashboard Statistics ==============
def _dashboard_stats():
    """Gather operational metrics for admin dashboard"""
    try:
        stats = {
            "total_users": User.objects.count(),
            "total_agents": User.objects.filter(role="agent").count(),
            "total_sellers": User.objects.filter(role="SELLER").count(),
            "unread_messages": Message.objects.filter(read_at__isnull=True).count() if Message else 0,
            "conversations": Conversation.objects.count() if Conversation else 0,
            "total_visitors": Visitor.objects.count() if Visitor else 0,
            "active_visitors": Visitor.objects.filter(
                last_seen__gte=timezone.now() - timezone.timedelta(minutes=15)
            ).count() if Visitor else 0,
        }
        
        # Add catalog statistics
        if Category:
            stats.update({
                "total_categories": Category.objects.filter(is_active=True).count(),
                "total_category_fields": CategoryField.objects.count() if CategoryField else 0,
            })
        else:
            stats.update({
                "total_categories": 0,
                "total_category_fields": 0,
            })
        
        # Add marketplace listings statistics
        if Listing:
            stats.update({
                "marketplace_listings": Listing.objects.filter(is_published=True).count(),
                "total_marketplace_listings": Listing.objects.count(),
            })
        else:
            stats.update({
                "marketplace_listings": 0,
                "total_marketplace_listings": 0,
            })
        
        # Add commerce statistics
        if Order:
            stats.update({
                "total_orders": Order.objects.count(),
                "pending_orders": Order.objects.filter(status="pending").count(),
                "completed_orders": Order.objects.filter(status="completed").count(),
            })
        else:
            stats.update({
                "total_orders": 0,
                "pending_orders": 0,
                "completed_orders": 0,
            })
        
        if Cart:
            stats.update({
                "active_carts": Cart.objects.count(),
            })
        else:
            stats.update({
                "active_carts": 0,
            })
        
        stats["timestamp"] = timezone.now()
        return stats
    except Exception as e:
        # During migrations/tests tables might not exist yet
        return {
            "total_users": "-",
            "total_agents": "-",
            "total_sellers": "-",
            "unread_messages": "-",
            "conversations": "-",
            "total_visitors": "-",
            "active_visitors": "-",
            "total_categories": "-",
            "total_category_fields": "-",
            "marketplace_listings": "-",
            "total_marketplace_listings": "-",
            "total_orders": "-",
            "pending_orders": "-",
            "completed_orders": "-",
            "active_carts": "-",
            "timestamp": timezone.now(),
        }


# ============== Dashboard Index ==============
_original_each_context = admin.site.each_context


def custom_each_context(request):
    """Extend admin context with dashboard statistics"""
    context = _original_each_context(request)
    stats = _dashboard_stats()

    # Format dashboard stats for display
    context["dashboard_stats"] = stats
    context["app_list_title"] = "Management"

    # Add quick stats display
    context["quick_stats"] = [
        {
            "label": "Total Users",
            "value": stats.get("total_users", "-"),
            "color": "blue",
            "icon": "👥",
        },
        {
            "label": "Marketplace Listings",
            "value": stats.get("marketplace_listings", "-"),
            "color": "green",
            "icon": "🛒",
        },
        {
            "label": "Categories",
            "value": stats.get("total_categories", "-"),
            "color": "indigo",
            "icon": "📁",
        },
        {
            "label": "Total Orders",
            "value": stats.get("total_orders", "-"),
            "color": "yellow",
            "icon": "📦",
        },
        {
            "label": "Unread Messages",
            "value": stats.get("unread_messages", "-"),
            "color": "purple",
            "icon": "💬",
        },
        {
            "label": "Total Visitors",
            "value": stats.get("total_visitors", "-"),
            "color": "teal",
            "icon": "👀",
        },
        {
            "label": "Active Now",
            "value": stats.get("active_visitors", "-"),
            "color": "red",
            "icon": "🟢",
        },
    ]

    return context


admin.site.each_context = custom_each_context


