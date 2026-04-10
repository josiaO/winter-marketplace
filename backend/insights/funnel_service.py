from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import Event

class FunnelService:
    """
    Service for calculating conversion funnel metrics and user journey analytics.
    """
    
    @staticmethod
    def get_conversion_funnel(days=30):
        """
        Calculate funnel stages and conversion rates.
        Stages:
        1. All Visitors (Unique sessions)
        2. Searchers (Users who searched)
        3. Property Viewers (Users who viewed details)
        4. Leads (Users who contacted agent or requested visit)
        """
        start_date = timezone.now() - timedelta(days=days)
        base_qs = Event.objects.filter(created_at__gte=start_date)
        
        # Stage 1: All Visitors
        total_visitors = base_qs.values('session_id').distinct().count() or 1 # Avoid division by zero
        
        # Stage 2: Searchers
        searchers = base_qs.filter(event_type='listing_search').values('session_id').distinct().count()
        
        # Stage 3: Listing Viewers
        viewers = base_qs.filter(event_type='listing_view').values('session_id').distinct().count()
        
        # Stage 4: Leads (Contact or Order Request)
        leads = base_qs.filter(event_type__in=['seller_contact', 'order_request']).values('session_id').distinct().count()
        
        return {
            "stages": [
                {
                    "id": "visitors",
                    "label": "Total Visitors",
                    "value": total_visitors,
                    "color": "#8884d8" 
                },
                {
                    "id": "searchers",
                    "label": "Performed Search",
                    "value": searchers,
                    "color": "#83a6ed"
                },
                {
                    "id": "viewers",
                    "label": "Viewed Listing",
                    "value": viewers,
                    "color": "#8dd1e1"
                },
                {
                    "id": "leads",
                    "label": "Contacted Seller/Ordered",
                    "value": leads,
                    "color": "#82ca9d"
                }
            ],
            "rates": {
                "visitor_to_lead": (leads / total_visitors) * 100 if total_visitors > 0 else 0,
                "view_to_lead": (leads / viewers) * 100 if viewers > 0 else 0
            }
        }
