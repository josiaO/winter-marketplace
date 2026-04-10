# Escrow engine — final audit (post-hardening)

## Production readiness score

**Estimated: 9 / 10** (up from ~7 / 10)

Remaining gap to “9.5+” is mostly **external**: Selcom transaction-status API for automatic reconciliation of stuck payouts (instead of fail + manual verify), and environment-specific tuning (Redis HA, Celery autoscaling, scrape auth for `/metrics/`).

## What improved

| Area | Change |
|------|--------|
| Gateway idempotency | `GatewayEvent` model with unique `(provider, event_id)`; webhooks stored before processing; duplicate delivery safe. |
| Gateway resilience | Selcom `initiate_payment`, `refund`, `disburse` use bounded retries + exponential backoff + 5s HTTP timeout per attempt. |
| Concurrency | Redis `lock()` for refund, payout, webhook processing; Django cache fallback if Redis client unavailable. |
| Atomics | Webhook/payout keep DB work split: short atomic → HTTP → short atomic (existing pattern extended). |
| Payout safety | Celery beat task `recover_stuck_payouts` fails stuck `PROCESSING` rows; admin actions retry / force-fail. |
| Observability | Prometheus metrics + `/api/v1/escrow/metrics/`; health endpoint; `escrow.failure` structured logs. |
| Throughput | Optional async webhooks via `ESCROW_WEBHOOK_ASYNC` + `process_gateway_webhook_event`. |
| API keys | IP allowlist, optional per-key RPM throttle, expiry, HTTP rotation endpoint. |
| Performance | Replaced `union()` queryset with `Q` filter + `select_related` / `prefetch_related`. |

## Residual risks

1. **Stuck payout recovery** marks `FAILED` without a live Selcom status check — operators must confirm before admin retry (avoids double disburse).
2. **Webhook async** requires Celery reliability; if workers lag, payment confirmation is delayed (provider retries help).
3. **`/metrics/` and `/health/`** are unauthenticated — protect at ingress (network policy / auth proxy) in production.
4. **IP allowlist** uses `X-Forwarded-For` first hop + `REMOTE_ADDR`; trust boundaries must match your proxy setup.

## Tests added

- `escrow_engine/tests/test_production_escrow.py`: `GatewayEvent` upsert, webhook idempotency (with lock mocked), stuck payout recovery, API key expiry + rotation HTTP path.

Run (with your normal Django test env / `.env`):

```bash
python manage.py test escrow_engine.tests
```
