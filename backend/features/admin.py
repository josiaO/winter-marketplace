from django.contrib import admin
from .models import Feature, Plan, PlanFeature, SubscriptionPlan

class PlanFeatureInline(admin.TabularInline):
    model = PlanFeature
    extra = 1

@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "status", "is_global")
    list_filter = ("status", "is_global")
    search_fields = ("name", "code")

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "price_monthly", "highlight")
    inlines = [PlanFeatureInline]

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'duration_days', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']

admin.site.register(PlanFeature)
