"""
escrow_engine.admin
--------------------
Full-coverage Django admin for the Escrow Engine.
Provides operational control over all financial models with:
  - Color-coded status badges
  - Bulk release / refund / payout actions
  - Audit log inlines (append-only)
  - Financial summary displays
  - Dispute resolution workflow
"""
import secrets

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.urls import NoReverseMatch, reverse
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import mark_safe

from .models import (
    Transaction, TransactionLog,
    Payout, PayoutDestination,
    Dispute, DisputeEvidence,
    APIKey,
    GatewayEvent,
    PaymentRecord,
    PaymentLink,
)
from .models.api_key import hash_api_key
from .state_machine import PaymentConfirmationSource, TransactionStatus


# ── Colour palette ──────────────────────────────────────────────────────────

STATUS_COLOURS = {
    TransactionStatus.CREATED:         ('#6c757d', '⬜'),
    TransactionStatus.PENDING_PAYMENT: ('#fd7e14', '🕐'),
    TransactionStatus.PAID:            ('#0d6efd', '💳'),
    TransactionStatus.HOLD:            ('#6f42c1', '🔒'),
    TransactionStatus.RELEASED:        ('#198754', '✅'),
    TransactionStatus.REFUNDED:        ('#20c997', '↩'),
    TransactionStatus.DISPUTED:        ('#dc3545', '⚠️'),
    TransactionStatus.FAILED:          ('#343a40', '❌'),
    TransactionStatus.CANCELLED:       ('#adb5bd', '🚫'),
}

def status_badge(status):
    colour, icon = STATUS_COLOURS.get(status, ('#6c757d', ''))
    return format_html(
        '<span style="background:{};color:white;padding:3px 10px;border-radius:12px;'
        'font-size:0.8rem;font-weight:600;">{} {}</span>',
        colour, icon, status.upper().replace('_', ' '),
    )


def admin_format_money(currency, amount) -> str:
    """
    Format currency + amount as plain text before passing to format_html.

    Django's format_html() wraps interpolations as SafeString; using ``{:,.2f}``
    in the template string then raises ValueError (float format on SafeString).
    Build a display string before format_html(). Do not use {:,.2f} on format_html()
    arguments — Django wraps them as SafeString and float formatting raises ValueError.
    """
    if amount is None:
        return f'{currency} —'
    try:
        return f'{currency} {float(amount):,.2f}'
    except (TypeError, ValueError):
        return f'{currency} {amount}'


def admin_user_change_url(user_id):
    """Reverse admin change URL for AUTH_USER_MODEL (e.g. auth_user_change)."""
    if user_id is None:
        return None
    User = get_user_model()
    return reverse(
        f'admin:{User._meta.app_label}_{User._meta.model_name}_change',
        args=[user_id],
    )

# ── Inlines ──────────────────────────────────────────────────────────────────

class TransactionLogInline(admin.TabularInline):
    model = TransactionLog
    extra = 0
    can_delete = False
    ordering = ['-created_at']
    readonly_fields = (
        'created_at', 'from_status_badge', 'to_status_badge',
        'actor_user', 'actor_label', 'reason', 'metadata',
    )
    fields = readonly_fields
    verbose_name = "Audit Entry"
    verbose_name_plural = "📋 Audit Trail (Append-Only)"

    def from_status_badge(self, obj):
        return status_badge(obj.from_status)
    from_status_badge.short_description = 'From'

    def to_status_badge(self, obj):
        return status_badge(obj.to_status)
    to_status_badge.short_description = 'To'


class PayoutInline(admin.StackedInline):
    model = Payout
    extra = 0
    can_delete = False
    readonly_fields = ('transaction_link', 'status_badge_display', 'amount', 'currency',
                       'payout_method', 'payout_reference', 'failure_reason',
                       'created_at', 'processed_at', 'completed_at')
    fields = readonly_fields
    verbose_name_plural = "💸 Payout Record"

    def status_badge_display(self, obj):
        colours = {'pending': '#fd7e14', 'processing': '#0d6efd', 'completed': '#198754', 'failed': '#dc3545'}
        c = colours.get(obj.status, '#6c757d')
        return format_html('<span style="background:{};color:white;padding:2px 8px;border-radius:4px;">{}</span>', c, obj.status)
    status_badge_display.short_description = 'Payout Status'

    def transaction_link(self, obj):
        url = reverse('admin:escrow_engine_transaction_change', args=[obj.transaction_id])
        return format_html('<a href="{}">{}</a>', url, obj.transaction.reference)
    transaction_link.short_description = 'Transaction'


class PaymentRecordInline(admin.TabularInline):
    """Gateway payment / refund log rows for this transaction."""

    model = PaymentRecord
    fk_name = 'transaction'
    extra = 0
    can_delete = False
    max_num = 0
    ordering = ['-created_at']
    show_change_link = True
    verbose_name_plural = '💳 Payment records (gateway log)'
    fields = (
        'created_at',
        'provider',
        'status',
        'amount_cell',
        'reference',
        'failure_excerpt',
    )
    readonly_fields = fields

    def amount_cell(self, obj):
        return admin_format_money(obj.currency, obj.amount)

    amount_cell.short_description = 'Amount'

    def failure_excerpt(self, obj):
        r = (obj.failure_reason or '').strip()
        if len(r) > 80:
            return r[:77] + '…'
        return r or '—'

    failure_excerpt.short_description = 'Failure'


class DisputeInline(admin.StackedInline):
    model = Dispute
    extra = 0
    readonly_fields = ('status', 'reason', 'opened_by', 'resolution_type', 'resolution',
                       'resolved_by', 'resolved_at', 'created_at')
    verbose_name_plural = "⚠️ Dispute"


class DisputeEvidenceInline(admin.TabularInline):
    model = DisputeEvidence
    extra = 0
    readonly_fields = ('submitted_by', 'file', 'media_type', 'caption', 'created_at')
    can_delete = False
    verbose_name_plural = "🗂 Evidence Files"


# ── Developer API Key Admin ─────────────────────────────────────────────────


class APIKeyAdminForm(forms.ModelForm):
    class Meta:
        model = APIKey
        fields = [
            'name',
            'is_active',
            'scopes',
            'ip_allowlist',
            'rate_limit_per_minute',
            'expires_at',
        ]


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    form = APIKeyAdminForm
    list_display = ['name', 'is_active', 'scopes_summary', 'created_at', 'last_used_at']
    list_filter = ['is_active', ('created_at', admin.DateFieldListFilter)]
    search_fields = ['name']
    readonly_fields = ['key_hash', 'created_at', 'updated_at', 'last_used_at']
    actions = ['deactivate_and_rotate_keys']

    fieldsets = (
        (None, {
            'fields': (
                'name',
                'is_active',
                'scopes',
                'ip_allowlist',
                'rate_limit_per_minute',
                'expires_at',
            ),
        }),
        ('Stored secret (hash only)', {
            'fields': ('key_hash', 'created_at', 'updated_at', 'last_used_at'),
            'classes': ('collapse',),
        }),
    )

    def scopes_summary(self, obj):
        return ', '.join(obj.scopes or []) or '—'

    scopes_summary.short_description = 'Scopes'

    def deactivate_and_rotate_keys(self, request, queryset):
        for old in queryset:
            raw = secrets.token_urlsafe(32)
            APIKey.objects.create(
                name=f'{old.name} (rotated)',
                key_hash=hash_api_key(raw),
                is_active=True,
                scopes=list(old.scopes or []),
                ip_allowlist=list(old.ip_allowlist or []),
                rate_limit_per_minute=old.rate_limit_per_minute,
                expires_at=old.expires_at,
            )
            old.is_active = False
            old.save(update_fields=['is_active', 'updated_at'])
            self.message_user(
                request,
                f'Rotated key "{old.name}". New secret (copy now): {raw}',
                level=messages.SUCCESS,
            )

    deactivate_and_rotate_keys.short_description = 'Deactivate selected & create rotated replacement(s)'

    def save_model(self, request, obj, form, change):
        if not change:
            raw = secrets.token_urlsafe(32)
            obj.key_hash = hash_api_key(raw)
            super().save_model(request, obj, form, change)
            self.message_user(
                request,
                f'API key created. Copy the secret now (shown once only): {raw}',
                level='SUCCESS',
            )
        else:
            super().save_model(request, obj, form, change)


# ── Transaction Admin ─────────────────────────────────────────────────────────

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'reference', 'status_badge_col', 'source', 'amount_display',
        'buyer_display', 'seller_display', 'payment_method',
        'auto_release_display', 'created_at',
    ]
    list_select_related = ('buyer_user', 'seller_user', 'linked_order')
    list_filter = [
        'status', 'source', 'currency', 'payment_method',
        ('created_at', admin.DateFieldListFilter),
    ]
    search_fields = [
        'reference', 'gateway_reference', 'external_reference',
        'buyer_user__username', 'seller_user__username',
        'buyer_phone', 'seller_phone', 'description',
    ]
    readonly_fields = [
        'id', 'reference', 'status_badge_col',
        'buyer_display', 'seller_display', 'linked_order_link',
        'financial_summary',
        'created_by_api_key',
        'created_at', 'updated_at', 'held_at', 'released_at',
        'refunded_at', 'auto_release_at', 'gateway_payload',
    ]
    fieldsets = (
        ('🔑 Identity', {
            'fields': ('id', 'reference', 'status_badge_col', 'source', 'description', 'created_by_api_key'),
        }),
        ('👤 Parties', {
            'fields': ('buyer_display', 'seller_display', 'buyer_phone', 'seller_phone'),
        }),
        ('💰 Financials', {
            'fields': ('financial_summary', 'amount', 'currency', 'payment_method',
                       'preferred_provider', 'gateway_reference', 'gateway_payload'),
        }),
        ('🔗 Links', {
            'fields': ('linked_order_link', 'auto_release_at'),
            'classes': ('collapse',),
        }),
        ('⏱ Timestamps', {
            'fields': ('created_at', 'updated_at', 'held_at', 'released_at', 'refunded_at'),
            'classes': ('collapse',),
        }),
    )
    inlines = [TransactionLogInline, PaymentRecordInline, PayoutInline, DisputeInline]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    list_per_page = 30
    show_full_result_count = False

    # ── Display helpers ──────────────────────────────────────────────────────

    def status_badge_col(self, obj):
        return status_badge(obj.status)
    status_badge_col.short_description = 'Status'
    status_badge_col.admin_order_field = 'status'

    def amount_display(self, obj):
        return format_html('<strong>{}</strong>', admin_format_money(obj.currency, obj.amount))
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'

    def buyer_display(self, obj):
        if obj.buyer_user:
            label = obj.buyer_user.get_full_name() or obj.buyer_user.username
            try:
                url = admin_user_change_url(obj.buyer_user_id)
                return format_html('<a href="{}">{}</a>', url, label)
            except NoReverseMatch:
                return label
            label = obj.buyer_user.get_full_name() or obj.buyer_user.username
            try:
                url = admin_user_change_url(obj.buyer_user_id)
                return format_html('<a href="{}">{}</a>', url, label)
            except NoReverseMatch:
                return label
        return obj.buyer_phone or '—'
    buyer_display.short_description = 'Buyer'
    buyer_display.admin_order_field = 'buyer_user'
    buyer_display.admin_order_field = 'buyer_user'

    def seller_display(self, obj):
        if obj.seller_user:
            label = obj.seller_user.get_full_name() or obj.seller_user.username
            try:
                url = admin_user_change_url(obj.seller_user_id)
                return format_html('<a href="{}">{}</a>', url, label)
            except NoReverseMatch:
                return label
            label = obj.seller_user.get_full_name() or obj.seller_user.username
            try:
                url = admin_user_change_url(obj.seller_user_id)
                return format_html('<a href="{}">{}</a>', url, label)
            except NoReverseMatch:
                return label
        return obj.seller_phone or '—'
    seller_display.short_description = 'Seller'
    seller_display.admin_order_field = 'seller_user'
    seller_display.admin_order_field = 'seller_user'

    def linked_order_link(self, obj):
        if obj.linked_order_id:
            url = reverse('admin:commerce_order_change', args=[obj.linked_order_id])
            return format_html('<a href="{}">Order #{}</a>', url, obj.linked_order_id)
        return '—'
    linked_order_link.short_description = 'Linked Order'

    def auto_release_display(self, obj):
        if obj.auto_release_at and obj.status == TransactionStatus.HOLD:
            delta = obj.auto_release_at - timezone.now()
            days = delta.days
            if days < 0:
                return format_html('<span style="color:#dc3545;">⏰ Overdue</span>')
            elif days <= 1:
                return format_html('<span style="color:#fd7e14;">⏰ {}h left</span>', int(delta.seconds / 3600))
            return format_html('<span style="color:#6f42c1;">⏰ {} days</span>', days)
        return '—'
    auto_release_display.short_description = 'Auto-Release'

    def financial_summary(self, obj):
        if not obj.linked_order_id:
            # Since there are no arguments to format, use mark_safe
            return mark_safe('<em>No linked order</em>')
        
        try:
            o = obj.linked_order
            st = admin_format_money(o.currency, o.subtotal)
            fee = admin_format_money(o.currency, o.platform_fee)
            ship = admin_format_money(o.currency, o.shipping_cost)
            seller = admin_format_money(o.currency, o.seller_payout_amount)
            return format_html(
                '<table style="border-collapse:collapse;width:100%;">'
                '<tr><td style="padding:4px 8px;background:#f8f9fa;">Subtotal</td>'
                '<td style="padding:4px 8px;"><strong>{}</strong></td></tr>'
                '<tr><td style="padding:4px 8px;background:#f8f9fa;">Platform Fee</td>'
                '<td style="padding:4px 8px;color:#dc3545;">{}</td></tr>'
                '<tr><td style="padding:4px 8px;background:#f8f9fa;">Shipping</td>'
                '<td style="padding:4px 8px;">{}</td></tr>'
                '<tr style="border-top:2px solid #dee2e6;">'
                '<td style="padding:4px 8px;background:#f8f9fa;"><strong>Seller Receives</strong></td>'
                '<td style="padding:4px 8px;color:#198754;"><strong>{}</strong></td></tr>'
                '</table>',
                st,
                fee,
                ship,
                seller,
            )
        except Exception:
            return '—'
    financial_summary.short_description = 'Financial Breakdown'

    # ── Bulk Actions ─────────────────────────────────────────────────────────

    actions = ['action_release_funds', 'action_refund_funds', 'action_hold_funds', 'action_confirm_payment']

    def action_release_funds(self, request, queryset):
        from escrow_engine.services.escrow import release_funds
        count = 0
        for txn in queryset.filter(status=TransactionStatus.HOLD):
            try:
                release_funds(txn, actor=request.user, actor_label=f'Admin: {request.user.username}', reason='Admin bulk release')
                count += 1
            except Exception as e:
                self.message_user(request, f'Error releasing {txn.reference}: {e}', level='error')
        self.message_user(request, f'✅ {count} transaction(s) released to seller.')
    action_release_funds.short_description = '✅ Release funds to seller'

    def action_refund_funds(self, request, queryset):
        from escrow_engine.services.escrow import refund_funds
        count = 0
        for txn in queryset.filter(status__in=[TransactionStatus.HOLD, TransactionStatus.DISPUTED]):
            try:
                refund_funds(txn, actor=request.user, actor_label=f'Admin: {request.user.username}', reason='Admin bulk refund')
                count += 1
            except Exception as e:
                self.message_user(request, f'Error refunding {txn.reference}: {e}', level='error')
        self.message_user(request, f'↩ {count} transaction(s) refunded to buyer.')
    action_refund_funds.short_description = '↩️ Refund funds to buyer'

    def action_hold_funds(self, request, queryset):
        from escrow_engine.services.escrow import hold_funds
        count = 0
        for txn in queryset.filter(status=TransactionStatus.PAID):
            try:
                hold_funds(txn, actor=request.user, actor_label=f'Admin: {request.user.username}', reason='Admin manual hold')
                count += 1
            except Exception as e:
                self.message_user(request, f'Error holding {txn.reference}: {e}', level='error')
        self.message_user(request, f'🔒 {count} transaction(s) moved to HOLD.')
    action_hold_funds.short_description = '🔒 Move to HOLD (if PAID)'

    def action_confirm_payment(self, request, queryset):
        from escrow_engine.services.payment import confirm_payment
        count = 0
        for txn in queryset.filter(status__in=[TransactionStatus.CREATED, TransactionStatus.PENDING_PAYMENT]):
            try:
                confirm_payment(
                    txn,
                    actor=request.user,
                    raw_payload={'admin_manual': True},
                    confirmation_source=PaymentConfirmationSource.ADMIN_MANUAL,
                )
                count += 1
            except Exception as e:
                self.message_user(request, f'Error confirming {txn.reference}: {e}', level='error')
        self.message_user(request, f'💳 {count} payment(s) manually confirmed and moved to HOLD.')
    action_confirm_payment.short_description = '💳 Manually confirm payment (→ HOLD)'


# ── TransactionLog Admin ──────────────────────────────────────────────────────

@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    """Read-only audit trail view. No adds, changes, or deletes allowed."""
    list_display = [
        'transaction_link', 'from_status_badge', 'to_status_badge',
        'actor_col', 'reason', 'created_at',
    ]
    list_select_related = ('transaction', 'actor_user')
    list_filter = ['from_status', 'to_status', ('created_at', admin.DateFieldListFilter)]
    search_fields = ['transaction__reference', 'actor_user__username', 'actor_label', 'reason']
    readonly_fields = [
        'transaction', 'from_status', 'to_status', 'actor_user',
        'actor_label', 'reason', 'metadata', 'created_at',
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False

    def transaction_link(self, obj):
        url = reverse('admin:escrow_engine_transaction_change', args=[obj.transaction_id])
        return format_html('<a href="{}">{}</a>', url, obj.transaction.reference)
    transaction_link.short_description = 'Transaction'

    def from_status_badge(self, obj):
        return status_badge(obj.from_status)
    from_status_badge.short_description = 'From'

    def to_status_badge(self, obj):
        return status_badge(obj.to_status)
    to_status_badge.short_description = 'To'

    def actor_col(self, obj):
        if obj.actor_label:
            return format_html('<em style="color:#6c757d;">{}</em>', obj.actor_label)
        if obj.actor_user:
            return obj.actor_user.username
        return '—'
    actor_col.short_description = 'Actor'


# ── Payout Admin ──────────────────────────────────────────────────────────────

@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'transaction_link', 'seller', 'amount_display',
        'payout_method', 'status_badge_col', 'payout_reference', 'created_at',
    ]
    list_select_related = ('transaction', 'seller')
    list_filter = ['status', 'payout_method', ('created_at', admin.DateFieldListFilter)]
    search_fields = ['seller__username', 'payout_reference', 'transaction__reference']
    readonly_fields = [
        'transaction_link', 'seller', 'amount', 'currency',
        'status', 'payout_method', 'payout_reference', 'failure_reason',
        'created_at', 'processed_at', 'completed_at',
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    actions = ['action_process_payouts', 'action_retry_payout', 'action_force_fail_processing']

    def status_badge_col(self, obj):
        colours = {
            'pending': '#fd7e14', 'processing': '#0d6efd',
            'completed': '#198754', 'failed': '#dc3545',
        }
        c = colours.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;">{}</span>',
            c, obj.status.upper()
        )
    status_badge_col.short_description = 'Status'

    def amount_display(self, obj):
        return format_html('<strong>{}</strong>', admin_format_money(obj.currency, obj.amount))
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'

    def transaction_link(self, obj):
        url = reverse('admin:escrow_engine_transaction_change', args=[obj.transaction_id])
        return format_html('<a href="{}">{}</a>', url, obj.transaction.reference)
    transaction_link.short_description = 'Transaction'

    def action_process_payouts(self, request, queryset):
        from escrow_engine.services.payout import process_payout
        count = 0
        for payout in queryset.filter(status__in=['pending', 'failed']):
            try:
                process_payout(payout)
                count += 1
            except Exception as e:
                self.message_user(request, f'Error processing payout #{payout.id}: {e}', level='error')
        self.message_user(request, f'💸 {count} payout(s) triggered for processing.')
    action_process_payouts.short_description = '💸 Trigger Payout Disbursement'

    def action_retry_payout(self, request, queryset):
        from escrow_engine.services.payout import process_payout

        count = 0
        for payout in queryset.filter(status__in=['pending', 'failed']):
            try:
                process_payout(payout)
                count += 1
            except Exception as e:
                self.message_user(request, f'Retry error payout #{payout.id}: {e}', level='error')
        self.message_user(request, f'🔁 {count} payout(s) retried.')
    action_retry_payout.short_description = '🔁 Retry payout (pending/failed)'

    def action_force_fail_processing(self, request, queryset):
        updated = queryset.filter(status='processing').update(
            status='failed',
            failure_reason='Admin force-fail: was processing',
        )
        self.message_user(request, f'⛔ {updated} processing payout(s) marked failed.')
    action_force_fail_processing.short_description = '⛔ Force-fail stuck processing payout(s)'


# ── Payout Destination Admin ──────────────────────────────────────────────────

@admin.register(PayoutDestination)
class PayoutDestinationAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'method_badge', 'account_number', 'account_name',
        'bank_code', 'is_default', 'created_at',
    ]
    list_select_related = ('user',)
    list_filter = ['method', 'is_default']
    search_fields = ['user__username', 'account_number', 'account_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['user__username']

    def method_badge(self, obj):
        CHANNEL_STYLES = {
            'mpesa':          ('#00a651', 'M-Pesa'),
            'tigo_pesa':      ('#0099cc', 'Tigo Pesa'),
            'airtel_money':   ('#e4001b', 'Airtel Money'),
            'halopesa':       ('#f7941d', 'HaloPesa'),
            'ezypesa':        ('#7b2d8b', 'EzyPesa'),
            'azampesa':       ('#005baa', 'AzamPesa'),
            'bank':           ('#17a2b8', 'Bank'),
            'card_visa':      ('#1a1f71', 'Visa'),
            'card_mastercard':('#eb001b', 'Mastercard'),
            'card_unionpay':  ('#c0392b', 'UnionPay'),
            'till':           ('#6f42c1', 'Till/QR'),
        }
        colour, label = CHANNEL_STYLES.get(obj.method, ('#6c757d', obj.method))
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:0.8rem;">{}</span>',
            colour, label,
        )
    method_badge.short_description = 'Channel'


# ── Dispute Admin ─────────────────────────────────────────────────────────────

@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'transaction_link', 'status_badge_col', 'resolution_type',
        'opened_by', 'resolved_by', 'created_at',
    ]
    list_select_related = ('transaction', 'opened_by', 'resolved_by')
    list_filter = [
        'status', 'resolution_type',
        ('created_at', admin.DateFieldListFilter),
    ]
    search_fields = [
        'transaction__reference', 'opened_by__username', 'reason', 'resolution',
    ]
    readonly_fields = ['transaction_link', 'opened_by', 'created_at', 'updated_at', 'resolved_at']
    inlines = [DisputeEvidenceInline]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    actions = ['action_resolve_release', 'action_resolve_refund', 'action_mark_under_review']

    fieldsets = (
        ('⚠️ Dispute Details', {
            'fields': ('transaction_link', 'opened_by', 'status', 'reason'),
        }),
        ('⚖️ Resolution', {
            'fields': ('resolution_type', 'resolution', 'resolved_by', 'resolved_at'),
        }),
        ('⏱ Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge_col(self, obj):
        colours = {
            'open': '#dc3545', 'under_review': '#fd7e14',
            'resolved': '#198754', 'closed': '#6c757d',
        }
        c = colours.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;">{}</span>',
            c, obj.status.upper().replace('_', ' ')
        )
    status_badge_col.short_description = 'Status'

    def transaction_link(self, obj):
        url = reverse('admin:escrow_engine_transaction_change', args=[obj.transaction_id])
        return format_html('<a href="{}">{}</a>', url, obj.transaction.reference)
    transaction_link.short_description = 'Transaction'

    def action_resolve_release(self, request, queryset):
        """Resolve dispute in seller's favour — release funds."""
        from escrow_engine.services.escrow import release_funds
        count = 0
        for dispute in queryset.filter(status__in=['open', 'under_review']):
            try:
                txn = dispute.transaction
                if txn.status == TransactionStatus.DISPUTED:
                    release_funds(
                        txn, actor=request.user,
                        actor_label=f'Admin: {request.user.username} (dispute resolved → release)',
                        reason=f'Dispute #{dispute.id} resolved in seller\'s favour'
                    )
                dispute.status = 'resolved'
                dispute.resolution_type = 'release_seller'
                dispute.resolved_by = request.user
                dispute.resolved_at = timezone.now()
                dispute.save()
                count += 1
            except Exception as e:
                self.message_user(request, f'Error: {e}', level='error')
        self.message_user(request, f'✅ {count} dispute(s) resolved — funds released to seller.')
    action_resolve_release.short_description = '✅ Resolve → Release to Seller'

    def action_resolve_refund(self, request, queryset):
        """Resolve dispute in buyer's favour — refund funds."""
        from escrow_engine.services.escrow import refund_funds
        count = 0
        for dispute in queryset.filter(status__in=['open', 'under_review']):
            try:
                txn = dispute.transaction
                if txn.status == TransactionStatus.DISPUTED:
                    refund_funds(
                        txn, actor=request.user,
                        actor_label=f'Admin: {request.user.username} (dispute resolved → refund)',
                        reason=f'Dispute #{dispute.id} resolved in buyer\'s favour'
                    )
                dispute.status = 'resolved'
                dispute.resolution_type = 'refund_buyer'
                dispute.resolved_by = request.user
                dispute.resolved_at = timezone.now()
                dispute.save()
                count += 1
            except Exception as e:
                self.message_user(request, f'Error: {e}', level='error')
        self.message_user(request, f'↩ {count} dispute(s) resolved — funds refunded to buyer.')
    action_resolve_refund.short_description = '↩️ Resolve → Refund to Buyer'

    def action_mark_under_review(self, request, queryset):
        updated = queryset.filter(status='open').update(status='under_review')
        self.message_user(request, f'🔍 {updated} dispute(s) marked as Under Review.')
    action_mark_under_review.short_description = '🔍 Mark as Under Review'


# ── Payment records (gateway log) ────────────────────────────────────────────


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    """Per-call gateway audit (initiate, webhook, refund); append-only."""

    list_display = [
        'id',
        'created_at',
        'transaction_link',
        'order_link',
        'provider',
        'status_badge',
        'amount_col',
        'reference_excerpt',
    ]
    list_select_related = ('transaction', 'order')
    list_filter = ['status', 'provider', ('created_at', admin.DateFieldListFilter)]
    search_fields = [
        'reference',
        'transaction__reference',
        'failure_reason',
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    readonly_fields = [f.name for f in PaymentRecord._meta.fields] + [
        'transaction_link',
        'order_link',
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def status_badge(self, obj):
        colours = {
            'pending': '#fd7e14',
            'completed': '#198754',
            'failed': '#dc3545',
            'reversed': '#6f42c1',
        }
        c = colours.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;">{}</span>',
            c,
            obj.status.upper(),
        )

    status_badge.short_description = 'Status'

    def amount_col(self, obj):
        return format_html('<span>{}</span>', admin_format_money(obj.currency, obj.amount))

    amount_col.short_description = 'Amount'

    def reference_excerpt(self, obj):
        r = (obj.reference or '').strip()
        if len(r) > 36:
            return r[:33] + '…'
        return r or '—'

    reference_excerpt.short_description = 'Reference'

    def transaction_link(self, obj):
        if not obj.transaction_id:
            return '—'
        url = reverse('admin:escrow_engine_transaction_change', args=[obj.transaction_id])
        return format_html('<a href="{}">{}</a>', url, obj.transaction.reference)

    transaction_link.short_description = 'Transaction'

    def order_link(self, obj):
        if not obj.order_id:
            return '—'
        try:
            url = reverse('admin:commerce_order_change', args=[obj.order_id])
            return format_html('<a href="{}">Order #{}</a>', url, obj.order_id)
        except Exception:
            return str(obj.order_id)

    order_link.short_description = 'Order'


# ── Payment links (shareable URLs) ──────────────────────────────────────────


@admin.register(PaymentLink)
class PaymentLinkAdmin(admin.ModelAdmin):
    """Operational control of shareable payment links."""

    list_display = [
        'token',
        'transaction_link',
        'created_by',
        'title_short',
        'is_used',
        'otp_verified',
        'expires_at',
        'valid_badge',
    ]
    list_select_related = ('transaction', 'created_by')
    list_filter = ['is_used', 'otp_verified', ('expires_at', admin.DateFieldListFilter)]
    search_fields = ['token', 'transaction__reference', 'buyer_phone_verified', 'title']
    readonly_fields = [
        'token',
        'transaction',
        'created_by',
        'used_at',
        'created_at',
        'updated_at',
        'pay_url_display',
    ]
    exclude = ('otp_code',)
    actions = ['action_clear_otp']

    fieldsets = (
        (None, {
            'fields': ('token', 'transaction', 'created_by', 'pay_url_display'),
        }),
        ('Display', {
            'fields': ('title', 'description'),
        }),
        ('Lifecycle', {
            'fields': ('expires_at', 'is_used', 'used_at'),
        }),
        ('Buyer / OTP', {
            'fields': ('otp_verified', 'otp_expires_at', 'buyer_phone_verified'),
            'description': 'Raw OTP is not shown in admin. Use “Clear OTP on link” if a buyer needs a fresh code.',
        }),
    )

    def title_short(self, obj):
        t = (obj.title or '').strip()
        if len(t) > 40:
            return t[:37] + '…'
        return t or '—'

    title_short.short_description = 'Title'

    def transaction_link(self, obj):
        url = reverse('admin:escrow_engine_transaction_change', args=[obj.transaction_id])
        return format_html('<a href="{}">{}</a>', url, obj.transaction.reference)

    transaction_link.short_description = 'Transaction'

    def pay_url_display(self, obj):
        u = obj.get_absolute_url()
        return format_html('<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>', u, u)

    pay_url_display.short_description = 'Public pay URL'

    def valid_badge(self, obj):
        ok = obj.is_valid
        c = '#198754' if ok else '#dc3545'
        label = 'valid' if ok else 'invalid'
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;">{}</span>',
            c,
            label,
        )

    valid_badge.short_description = 'Valid'

    def action_clear_otp(self, request, queryset):
        updated = queryset.update(
            otp_code='',
            otp_expires_at=None,
            otp_verified=False,
        )
        self.message_user(request, f'Cleared OTP fields on {updated} link(s).')

    action_clear_otp.short_description = 'Clear OTP on selected links (buyer can request again)'


# ── Gateway webhook idempotency (read-only) ──────────────────────────────────


@admin.register(GatewayEvent)
class GatewayEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'provider', 'event_id_short', 'status', 'transaction_link', 'created_at']
    list_select_related = ('transaction',)
    list_filter = ['provider', 'status', ('created_at', admin.DateFieldListFilter)]
    search_fields = ['event_id', 'transaction__reference']
    readonly_fields = [
        'id', 'provider', 'event_id', 'transaction', 'payload', 'processed_at',
        'status', 'error_message', 'created_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def event_id_short(self, obj):
        s = obj.event_id
        return (s[:48] + '…') if len(s) > 48 else s

    event_id_short.short_description = 'event_id'

    def transaction_link(self, obj):
        if not obj.transaction_id:
            return '—'
        url = reverse('admin:escrow_engine_transaction_change', args=[obj.transaction_id])
        return format_html('<a href="{}">{}</a>', url, obj.transaction.reference)

    transaction_link.short_description = 'Transaction'
