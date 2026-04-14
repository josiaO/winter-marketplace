from django.contrib import admin

from sellers.models import (
    SellerActionLog,
    SellerOnboardingProgress,
    SellerPayoutAccount,
)


@admin.register(SellerPayoutAccount)
class SellerPayoutAccountAdmin(admin.ModelAdmin):
    list_display = ('seller', 'account_type', 'account_number', 'is_verified', 'is_primary')
    raw_id_fields = ('seller',)


@admin.register(SellerOnboardingProgress)
class SellerOnboardingProgressAdmin(admin.ModelAdmin):
    list_display = ('seller', 'step_registration', 'step_store_setup', 'step_id_approved', 'step_payout_added')
    raw_id_fields = ('seller',)


@admin.register(SellerActionLog)
class SellerActionLogAdmin(admin.ModelAdmin):
    list_display = ('seller', 'action', 'performed_by', 'timestamp')
    raw_id_fields = ('seller', 'performed_by')
