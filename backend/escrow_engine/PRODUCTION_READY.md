# Escrow engine — production operations

This document describes how the hardened escrow/payment engine behaves in production and how to operate it.

## Architecture (text)

```
[Client / Marketplace / Developer API]
        │
        ▼
┌───────────────────┐     ┌─────────────────┐
│   Django + DRF    │────▶│  PostgreSQL     │  (transactions, payouts, GatewayEvent, APIKey)
└─────────┬─────────┘     └─────────────────┘
          │
          ├──────────────────▶ Redis (cache + distributed locks via django-redis)
          │
          ├──────────────────▶ Celery workers (optional async webhooks, beat tasks)
          │
          └──────────────────▶ Selcom (checkout, refund, qwiksend/disburse)
```

## Flows

### Payment (checkout)

1. `initiate_payment` transitions `CREATED` → `PENDING_PAYMENT` (if needed) and calls Selcom `create-order-minimal` with **retries** (3×, exponential backoff, 5s timeout per attempt).
2. Idempotent re-init uses `payment_idempotency_key` in `Transaction.metadata` when status is already `PENDING_PAYMENT` and a gateway reference exists.
3. In `DEBUG` with mock Selcom payload, payment may auto-confirm (unchanged dev behaviour).

### Webhook

1. HTTP `POST` `/api/v1/escrow/webhooks/selcom/` verifies HMAC (`Digest` / `Timestamp`) unless `DEBUG` skips.
2. Payload is stored as `GatewayEvent` with `(provider, event_id)` unique; `event_id` is derived from provider fields or a hash of the canonical JSON.
3. If the event is already **processed / duplicate / failed**, the handler returns **200** without re-running side effects.
4. Otherwise a **Redis lock** `escrow:webhook:{provider}:{event_id}` serializes processing.
5. When `ESCROW_WEBHOOK_ASYNC` is **True** in Django settings, the view **acks immediately** and enqueues `process_gateway_webhook_event` on commit; workers call the same execution path as sync mode.

### Payout

1. `process_payout` moves row to `PROCESSING` inside a short DB transaction, **commits**, then calls Selcom disburse with retries.
2. A second atomic block finalizes `COMPLETED` or `FAILED`.
3. A **Redis lock** `escrow:payout:{id}` prevents concurrent `process_payout` on the same row across instances.
4. **Celery beat** runs `recover_stuck_payouts` every 15 minutes (code schedule in `settings.CELERY_BEAT_SCHEDULE`): payouts in `PROCESSING` older than `ESCROW_STUCK_PAYOUT_MINUTES` (default 30) are marked `FAILED` with an explicit reason so operators can verify with the provider before admin retry.

### Refund

1. Redis lock `escrow:refund:{transaction_id}` (cache fallback if Redis client fails).
2. DB state check → gateway `reverse-order` (retries) **outside** the first atomic → final transition to `REFUNDED`.

## Failure handling

- Structured errors: `log_escrow_failure(event='escrow.failure', severity='critical', ...)` for alert pipelines.
- Prometheus counters/histograms (see `/api/v1/escrow/metrics/`): payments, webhooks, payout latency.
- **Health**: `GET /api/v1/escrow/health/` — database, Redis ping, Celery worker ping (best-effort).

## Developer API keys

- Optional **IP allowlist** (`ip_allowlist`), **per-key rate limit** (`rate_limit_per_minute` + `EscrowDeveloperAPIKeyThrottle`), **expiry** (`expires_at`).
- **Rotation**: `POST /api/v1/escrow/dev/keys/rotate/` with current `X-Api-Key` (or Django admin “Deactivate & rotate”).

## Recommended production toggles

| Setting | Purpose |
|--------|---------|
| `ESCROW_WEBHOOK_ASYNC = True` | Fast webhook 200 + Celery processing (requires workers). |
| `ESCROW_STUCK_PAYOUT_MINUTES` | Stuck `PROCESSING` threshold for recovery task. |
| Redis for `CACHES['default']` | Required for meaningful distributed locks. |

## Query performance

Main user transaction list uses a single `Q(buyer_user=user) \| Q(seller_user=user)` with `select_related` / `prefetch_related` instead of `union()`.
