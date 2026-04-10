from django.contrib import admin
from .models import (
    DailyMetric, Visitor, Event, 
    ListingEngagement, SellerLeadMetrics, 
    GeographicInsight, WeeklyEngagementPattern
)


@admin.register(DailyMetric)
class DailyMetricAdmin(admin.ModelAdmin):
    list_display = ("date", "views", "leads", "conversions", "conversion_rate")
    list_filter = ("date",)
    search_fields = ("date",)
    ordering = ("-date",)
    date_hierarchy = "date"

    def conversion_rate(self, obj):
        if obj.leads > 0:
            return f"{(obj.conversions / obj.leads) * 100:.1f}%"
        return "0%"
    conversion_rate.short_description = "Conversion Rate"


@admin.register(Visitor)
class VisitorAdmin(admin.ModelAdmin):
    list_display = ("session_key", "ip_address", "visit_count", "first_seen", "last_seen")
    search_fields = ("session_key", "ip_address")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "user", "session_id", "device_type", "created_at")
    list_filter = ("event_type", "device_type", "created_at")
    search_fields = ("session_id", "user__email", "ip_address")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(ListingEngagement)
class ListingEngagementAdmin(admin.ModelAdmin):
    list_display = ("listing", "total_shares", "total_contact_attempts", "total_likes", "updated_at")
    search_fields = ("listing__title",)


@admin.register(SellerLeadMetrics)
class SellerLeadMetricsAdmin(admin.ModelAdmin):
    list_display = ("seller", "date", "new_messages", "conversations_started", "updated_at")
    list_filter = ("date",)
    search_fields = ("seller__username", "seller__email")


@admin.register(GeographicInsight)
class GeographicInsightAdmin(admin.ModelAdmin):
    list_display = ("location_name", "seller", "view_count", "date")
    list_filter = ("date",)
    search_fields = ("location_name", "seller__username")


@admin.register(WeeklyEngagementPattern)
class WeeklyEngagementPatternAdmin(admin.ModelAdmin):
    list_display = ("seller", "week_start_date", "day_of_week", "activity_level")
    list_filter = ("week_start_date", "day_of_week", "activity_level")
    search_fields = ("seller__username",)
