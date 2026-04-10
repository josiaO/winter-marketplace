# Escrow engine — post-hardening evaluation

This document summarizes the state of `escrow_engine` after the production hardening pass (API keys, authorization, payouts, transactions, records, and uploads).

## 1. Fixes applied (by phase)

**Phase 1 — critical**

- **Developer API**: `APIKey` model (hashed secret, `name`, `is_active`, `scopes`), `Transaction.created_by_api_key`, `APIKeyAuthentication` + scoped permissions, querysets restricted to the caller’s key; admin creates keys and shows the plaintext secret once.
- **Pay authorization**: Main `TransactionViewSet` uses `IsTransactionParty` and `self.get_object()` in `pay` so object-level checks and queryset scoping apply.
- **Disputes**: `Q` import fixed; `DisputeViewSet.create` routes through `open_dispute` with buyer-or-admin checks; developer dispute create validates reason length.
- **OTP**: Removed OTP and full phone from logs; verification log no longer includes phone.
- **Payouts**: `disburse(..., amount=...)` uses `Payout.amount`; Selcom payload uses that amount.
- **Serializer**: Developer `TransactionSerializer` field `refund_at` renamed to `refunded_at`.

**Phase 2 — hardening**

- **`transaction.atomic()`**: `confirm_payment`, `hold_funds`, `release_funds`, `refund_funds` (with a note that `refund_funds` holds the DB transaction across the gateway HTTP call).
- **`select_for_update()`**: Webhook handling, `create_payout` / `process_payout`, auto-release Celery task (`skip_locked` per row).
- **`PaymentRecord`**: Writes on payment initiation, payment confirmation, gateway refund attempts, and **webhook outcomes** (verify failure, unknown transaction, idempotent duplicate delivery).
- **Payment-link throttling**: `EscrowPaymentLinkScopedThrottle` on OTP request/verify and link pay; default rates live in `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['escrow_payment_link']` in project settings (tunable in code, no `.env` required).
- **Regression tests**: `escrow_engine/tests/` (developer API, pay/dispute auth, payout amount, webhook records, OTP logs, throttling).
- **Buyer-only pay** (main `TransactionViewSet`): `pay` uses `IsTransactionBuyer` (staff exempt); sellers no longer hit checkout on behalf of buyers on that endpoint. Payment-link `InitiateLinkPaymentView` unchanged (anonymous / OTP flow).
- **Payment idempotency**: optional `idempotency_key` on `initiate_payment` and serializers; repeats return the stored checkout URL / gateway reference (metadata on `Transaction`).
- **Narrower DB + HTTP separation**: `refund_funds` runs gateway HTTP outside `atomic()` with a cache lock; `process_payout` sets `PROCESSING` then calls `disburse` outside the first transaction.
- **Webhook duplicate `PaymentRecord` sampling**: at most one `webhook_idempotent_duplicate` row per transaction / reference / hour.
- **Structured metric logs**: `escrow_engine.metrics` logger — `log_escrow_metric(event=..., key=value)` for payment, webhook, payout, refund, hold, release.
- **Escrow security headers**: `EscrowSecurityHeadersMiddleware` for `/api/v1/escrow/*` and `/api/v1/transactions/*`.
- **API key rotation**: admin action “Deactivate selected & create rotated replacement(s)” plus existing `last_used_at` on use.
- **`PayoutDestination`**: Partial unique constraint — at most one `is_default=True` per user, plus data migration to dedupe existing rows.
- **Uploads**: Dispute seller `respond` validates file size and MIME type (settings: `ESCROW_DISPUTE_UPLOAD_MAX_BYTES`, `ESCROW_DISPUTE_UPLOAD_CONTENT_TYPES`).

## 2. Code changes (summary by area)

| Area | Files touched |
|------|----------------|
| API keys | `models/api_key.py`, `models/transaction.py`, `models/__init__.py`, `api/authentication.py`, `api/permissions.py`, `api/views.py`, `admin.py`, `migrations/0002_*` |
| Services | `services/transaction.py`, `services/payment.py`, `services/escrow.py`, `services/payout.py`, `services/payment_records.py`, `tasks.py` |
| Public API | `views.py`, `serializers.py`, `upload_validation.py` |
| Provider | `providers/base.py`, `providers/selcom.py` |
| Models | `models/payout.py`, `migrations/0003_*` |
| Developer serializers | `api/serializers.py` |
| Throttling | `throttling.py`, project `settings.py` (`escrow_payment_link` rate) |
| Tests | `tests/test_developer_api.py`, `tests/test_services_and_flows.py` |
| Metrics / middleware | `services/metrics_log.py`, `middleware.py`, `settings.py` (`MIDDLEWARE`) |

## 3. Short explanation per theme

- **API keys**: Stops “any non-empty header” access; scopes limit destructive actions; rows are tenant-scoped by `created_by_api_key`.
- **Pay / disputes**: Prevents IDOR-style pay on arbitrary UUIDs and removes unsafe generic dispute `create` on the main API.
- **OTP logging**: Reduces credential leakage in log aggregators.
- **Payout amount**: Aligns Selcom disbursement with the fee-adjusted `Payout` row to avoid over-paying sellers on marketplace orders.
- **Atomic + locks**: Reduces double webhook confirm, double payout processing, and concurrent auto-release races.
- **PaymentRecord**: Gives an auditable trail for initiation, confirmation, refunds, and webhook-side outcomes (including failed verification and duplicate notifications).
- **Throttling**: Reduces OTP / payment-link abuse; adjust `escrow_payment_link` in `DEFAULT_THROTTLE_RATES` if legitimate traffic is blocked.
- **One default payout destination**: Avoids ambiguous disbursement routing.
- **Upload validation**: Reduces abuse via huge or unexpected file types on dispute evidence.

## 4. Final evaluation

### Is it production-ready now?

**Closer, but not a blanket “yes.”** Core authorization and money-path consistency are significantly improved. Production readiness still depends on: human-operated environment configuration (Selcom secrets, webhook URLs, `DEBUG=False`), monitoring, backup/disaster recovery, and legal/compliance review for your jurisdiction. Payment-link rate limits are configured in code/settings (`escrow_payment_link`), not `.env`.

### What risks remain?

- **External gateways**: Idempotency and timeouts on Selcom (and any future PSP) are not fully abstracted; network failures during `refund_funds` still need operational playbooks.
- **Webhook security & replay**: Signature verification exists; replay/idempotency keys and clock skew policies should be validated against Selcom’s docs in production.
- **Long transactions**: `refund_funds` (and payout `process_payout`) can hold DB transactions open across HTTP; under load, pool exhaustion is possible—consider narrowing atomic sections later.
- **Developer API keys**: No built-in rotation UI, per-key rate limits, or IP allowlists (optional hardening).
- **Celery**: Tasks are at-least-once; auto-release now uses row locks but worker crashes mid-flight still need reconciliation jobs.

### What would break (or hurt) at ~10,000 users?

- **DB contention**: Hot rows (`select_for_update` on the same transaction from webhooks + admin + tasks) can queue; indexes and connection pool sizing matter.
- **Webhook throughput**: Sustained spikes may backlog if processing is synchronous in the web tier.
- **`union()` in `TransactionViewSet.get_queryset`**: Can become expensive at scale; consider replacing with a single `Q` filter if profiling shows it as a bottleneck.
- **Selcom rate limits**: Aggregator throttling could stall payouts or checkouts without retries/backoff (not all implemented here).

### Production score (0–10)

**7 / 10** — Same baseline hardening as before, plus webhook audit rows, payment-link throttling (settings-driven), and a focused regression test suite; still not “large PSP” maturity without observability, SLOs, chaos testing, and formal reconciliation.

### Remaining improvements (non-critical — mostly human / external)

- **Alerting & dashboards**: Point Prometheus / Datadog / CloudWatch at `escrow_metric` log lines or add native exporters; define SLOs and on-call playbooks (operations).
- **PSP-native idempotency**: If Selcom (or others) expose event IDs or idempotency tokens in webhooks, persist and dedupe on those fields in addition to gateway reference.
- **Payout stuck in `processing`**: Add a periodic job or admin action to fail or retry payouts left in `processing` after a timeout (crashed worker after a successful HTTP call needs reconciliation with the PSP).
- **Refund cache lock**: Uses Django’s default cache; use a **shared** Redis/Memcached in multi-instance production so the lock is cluster-wide.
- **CAPTCHA / WAF**: Front payment-link URLs with edge protection if abuse continues (infrastructure).
- **Optional**: Buyer delegates pay to seller again — would require an explicit product flag + permission, not enabled by default.
