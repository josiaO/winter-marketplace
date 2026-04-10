from django.contrib import admin
from django.utils.html import format_html
from .models import SellerStats, PlatformMetrics


@admin.register(SellerStats)
class SellerStatsAdmin(admin.ModelAdmin):
    list_display = [
        'seller', 'total_listings', 'active_listings', 'sold_listings',
        'total_orders', 'completed_orders', 'total_revenue', 'average_rating',
        'total_reviews', 'last_calculated_at',
    ]
    list_filter = ['currency']
    search_fields = ['seller__username', 'seller__email']
    readonly_fields = ['last_calculated_at']
    actions = ['recalculate_stats']

    @admin.action(description="Recalculate stats for selected sellers")
    def recalculate_stats(self, request, queryset):
        for stats in queryset:
            stats.calculate_stats()
        self.message_user(request, f"Recalculated stats for {queryset.count()} seller(s).")



@admin.register(PlatformMetrics)
class PlatformMetricsAdmin(admin.ModelAdmin):
    list_display = [
        'date', 'total_users', 'new_users_today', 'active_users_today',
        'total_listings', 'active_listings', 'total_orders', 'orders_today',
        'revenue_today_display', 'average_trust_score', 'verified_users',
    ]
    list_filter = ['currency']
    date_hierarchy = 'date'
    readonly_fields = ['date']
    ordering = ['-date']
    actions = ['recalculate_metrics']

    def revenue_today_display(self, obj):
        return format_html('<b>{} {:,.2f}</b>', obj.currency, obj.revenue_today)
    revenue_today_display.short_description = "Revenue Today"

    @admin.action(description="Recalculate metrics for selected dates")
    def recalculate_metrics(self, request, queryset):
        for metric in queryset:
            PlatformMetrics.calculate_for_date(metric.date)
        self.message_user(request, f"Recalculated metrics for {queryset.count()} date(s).")