from django.contrib import admin

from sellers.models import (
    SellerActionLog,
    SellerBusinessVerification,
    SellerIDVerification,
    SellerOnboardingProgress,
    SellerPayoutAccount,
)


@admin.register(SellerIDVerification)
class SellerIDVerificationAdmin(admin.ModelAdmin):
    list_display = ('seller', 'id_type', 'submitted_at', 'reviewed_at')
    raw_id_fields = ('seller', 'reviewed_by')


@admin.register(SellerPayoutAccount)
class SellerPayoutAccountAdmin(admin.ModelAdmin):
    list_display = ('seller', 'account_type', 'account_number', 'is_verified', 'is_primary')
    raw_id_fields = ('seller',)


@admin.register(SellerOnboardingProgress)
class SellerOnboardingProgressAdmin(admin.ModelAdmin):
    list_display = ('seller', 'step_registration', 'step_store_setup', 'step_id_approved', 'step_payout_added')
    raw_id_fields = ('seller',)


@admin.register(SellerBusinessVerification)
class SellerBusinessVerificationAdmin(admin.ModelAdmin):
    list_display = ('seller', 'business_name', 'status', 'submitted_at')
    raw_id_fields = ('seller', 'reviewed_by')


@admin.register(SellerActionLog)
class SellerActionLogAdmin(admin.ModelAdmin):
    list_display = ('seller', 'action', 'performed_by', 'timestamp')
    raw_id_fields = ('seller', 'performed_by')
