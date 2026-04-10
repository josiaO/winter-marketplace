# Escrow Engine — App Documentation

This document describes the **escrow_engine** Django application: its role in SmartDalali, data model, APIs, business logic, observability, and a **production-readiness audit** (security, performance, consistency, tests).

**Code locations (quick map)**

| Area | Path |
|------|------|
| Models | `models/` (`transaction`, `dispute`, `payout`, `payment_record`, `payment_link`, `audit`, **`api_key`**, **`gateway_event`**) |
| State machine | `state_machine.py` (`TransactionStatus`, `PaymentConfirmationSource`) |
| Services | `services/` (`transaction`, `payment`, `escrow`, `payout`, `payment_link_service`, **`payment_records`**, **`webhook_ids`**, **`distributed_lock`**, **`metrics_log`**, **`gateway_retry`**, **`linked_order`**) |
| Payment providers | `providers/` (`selcom`, `registry`, `base`) |
| Main HTTP API | `views.py`, `urls.py` (mounted at `/api/v1/escrow/`) |
| Developer API | `api/` (`views.py`, `urls.py`, **`authentication.py`**, **`permissions.py`**, **`throttling.py`**, `serializers.py`) |
| User-facing serializers | `serializers.py` |
| Permissions (main API) | `permissions.py` |
| Rate limits (payment links) | `throttling.py` |
| Upload validation | `upload_validation.py` |
| Celery | `tasks.py` |
| Admin | `admin.py` |
| Observability | `prometheus_metrics.py`, `middleware.py` |
| Signals | `signals.py` (no financial sync handlers — see note in file) |
| Tests | `tests/` |

**Related docs in this app:** `PRODUCTION_READY.md`, `PRODUCTION_EVALUATION.md`, `ESCROW_FINAL_AUDIT.md` (may overlap with this README; **this file is the primary developer-oriented overview**).

---

## 1. App overview

### 1.1 Purpose

**escrow_engine** is the **universal escrow and payments orchestration layer**. It owns:

- A single **`Transaction`** model as the financial source of truth (amount, status, gateway trace, parties, optional API key provenance).
- A **strict state machine** for the transaction lifecycle.
- **Selcom** (primary) integration: hosted checkout, server-side order status verification, webhooks, refunds, disbursements.
- **Payouts** with **row-level locking**, **PROCESSING** state, and **recovery** tasks for stuck rows.
- **Disputes** and evidence (with **upload validation** on seller responses).
- **Payment links** (public token URLs, **scoped throttling**, OTP flow without logging secrets).
- **Gateway idempotency** via **`GatewayEvent`** (unique `provider` + `event_id`) and optional **async** webhook processing (`ESCROW_WEBHOOK_ASYNC` + Celery).

### 1.2 Role in the system

| Concern | Role of escrow_engine |
|---------|------------------------|
| Marketplace checkout | `Transaction.linked_order` → `commerce.Order`; `services/escrow.py` syncs order status on hold/release/refund |
| Seller payout | `Payout` + `PayoutDestination`; marketplace signals sync seller methods into destinations |
| Policy timers | Celery tasks for **delivered-order auto-release** and **`auto_release_at`** (task exists; see §10 for Beat coverage) |
| Analytics / dashboards | `insights`, `analytics`, `commerce` read engine models |
| Developer integrations | **`APIKey`**-scoped HTTP API under `/api/v1/transactions/` and mirrored under `/api/v1/escrow/dev/` |

### 1.3 Core vs supporting

**Core** for any flow that moves money or escrow state. **Not optional** when marketplace payments and payouts are enabled.

---

## 2. Models audit

### 2.1 `Transaction` (`models/transaction.py`)

| Field / group | Purpose |
|---------------|---------|
| `id` (UUID PK) | Stable identifier |
| `reference` | Unique human-readable reference (`TXN-…`) |
| `amount`, `currency` | Escrow amount |
| `status` | Lifecycle (`TransactionStatus`) |
| `source` | `marketplace` / `external` / `api` |
| Party fields | `buyer_user`, `seller_user`, phones/emails |
| `external_reference` | Third-party correlation |
| `created_by_api_key` | **FK** to `APIKey` — set for Developer API–created rows; used to **scope** dev API querysets |
| Gateway fields | `payment_method`, `gateway_reference`, `gateway_payload` |
| `linked_order` | **OneToOne** to `commerce.Order` (optional) |
| Dispute shortcuts | `dispute_resolved_by`, `dispute_reason` |
| `metadata`, timestamps, `auto_release_at`, `preferred_provider` | Context / scheduling |

**Relationships:** FKs to users; OneToOne to `Order`; FK to `APIKey` (nullable).

**Indexing:** Composite indexes on `status`, `source`, users, `gateway_reference` (see model `Meta`).

**Validation:** `clean()` validates transitions on update; `save()` calls `clean()`.

**Signals:** None on the model; financial sync with orders is **explicit** in `commerce.services.lifecycle` and escrow services (not Django signals).

**Fat model note:** `transition_to()` updates status in SQL, refreshes, appends `TransactionLog`. Callers increasingly wrap critical paths in **`transaction.atomic()`** + **`select_for_update`** in services (e.g. `hold_funds`, `release_funds`, `create_payout`).

**Residual gaps:** No DB constraint `amount > 0`; optional `ESCROW_PARANOID_MODE` in settings for stricter order↔escrow checks elsewhere.

---

### 2.2 `APIKey` (`models/api_key.py`)

| Field | Purpose |
|-------|---------|
| `name` | Label |
| `key_hash` | **SHA-256** of secret (unique, indexed) |
| `is_active` | Revocation |
| `ip_allowlist` | Optional JSON list of allowed client IPs (evaluated against `X-Forwarded-For` / `REMOTE_ADDR`) |
| `rate_limit_per_minute` | Optional per-key cap (used by `EscrowDeveloperAPIKeyThrottle`) |
| `expires_at` | Optional expiry |
| `scopes` | JSON list: `read`, `write`, `pay`, `refund`, `release` |
| `last_used_at` | Updated on successful auth |

**Authentication:** `api/authentication.py` — header `X-Api-Key` → hash lookup. **Plaintext secret is never stored.**

---

### 2.3 `GatewayEvent` (`models/gateway_event.py`)

Idempotent storage of inbound webhooks: **`UniqueConstraint(provider, event_id)`**. Tracks `status` (`pending`, `processed`, `duplicate`, `failed`), payload, linked `transaction`, errors.

---

### 2.4 `TransactionLog` (`models/audit.py`)

Append-only audit rows per transition (actor user/label, reason, metadata). Enforced in admin (`can_delete = False`), not at DB level.

---

### 2.5 `PayoutDestination` (`models/payout.py`)

Seller payout routing. **`UniqueConstraint`** on `(user)` **where `is_default`** — at most **one** default destination per user (migration `0003`).

---

### 2.6 `Payout` (`models/payout.py`)

**OneToOne** to `Transaction`. Statuses include **`processing`** between pending HTTP disburse and completion/failure.

**Disbursement amount:** `process_payout` passes **`payout.amount`** (from `_calculate_payout_amount`) into `SelcomProvider.disburse(..., amount=pay_amount)` — aligns net seller amount with order fees when linked to an order.

---

### 2.7 `Dispute` / `DisputeEvidence` (`models/dispute.py`)

One `Dispute` per `Transaction`. File fields on dispute + evidence rows. **API-layer validation** for counter-evidence: `upload_validation.validate_dispute_upload_file` (size + MIME allowlist; settings `ESCROW_DISPUTE_UPLOAD_*`).

---

### 2.8 `PaymentRecord` (`models/payment_record.py`)

Append-only gateway/payment audit rows. **Written** via `services/payment_records.write_payment_record()` from **`services/payment.py`** and **`services/escrow.py`** (initiation, confirmation, refunds, etc.).

---

### 2.9 `PaymentLink` (`models/payment_link.py`)

Shareable token, expiry, OTP fields, `buyer_phone_verified`. Indexed for token/expiry queries.

---

## 3. Business logic

### 3.1 Where logic lives

| Layer | Responsibility |
|-------|----------------|
| **`services/`** | Transactions, payments, webhooks, escrow moves, disputes, payouts, payment links, metrics hooks |
| **`state_machine.py`** | Allowed transitions; `PaymentConfirmationSource` for how payment was confirmed |
| **`models/transaction.py`** | `transition_to`, `clean` |
| **`providers/`** | Selcom HTTP, signatures, server-side verification where configured |
| **`views.py`** | HTTP adapters; delegate to services |

### 3.2 Service layer entrypoints (`services/__init__.py`)

`create_transaction`, `get_transaction`, `initiate_payment`, `confirm_payment`, `handle_webhook`, `hold_funds`, `release_funds`, `refund_funds`, `open_dispute`, `resolve_dispute`, `create_payout`, `process_payout`.

### 3.3 Notable behaviors

| Topic | Detail |
|-------|--------|
| **Webhook pipeline** | `upsert_gateway_webhook_event` → optional Celery `process_gateway_webhook_event` → `execute_webhook_for_stored_event` with **Redis distributed lock** per `(provider, event_id)` |
| **Payment confirmation audit** | `confirm_payment(..., confirmation_source=...)` records source (`webhook`, `admin_manual`, `dev_mock`, etc.) |
| **Idempotency** | Initiate payment supports **idempotency keys** (serializer + service) to reduce duplicate gateway orders |
| **Commerce coupling** | `services/escrow.py` still imports `commerce.models.Order` for post-hold/release/refund sync |
| **View logic** | `DisputeViewSet.respond` still embeds workflow (notes + uploads); could move to a dispute service |

---

## 4. API layer (DRF)

### 4.1 Main API — `/api/v1/escrow/` (`urls.py`)

**`TransactionViewSet`** (`basename='engine-transaction'`)

| Method | Path | Purpose | Permissions |
|--------|------|---------|-------------|
| GET/POST | `/transactions/` | List / create (create forces `source=api` in view) | `IsAuthenticated` + **`IsTransactionParty`** (object-level for retrieve) |
| GET | `/transactions/{uuid}/` | Retrieve | Same |
| POST | `/transactions/{uuid}/pay/` | Initiate payment | **`IsAuthenticated` + `IsTransactionBuyer`** (only buyer may pay) |
| POST | `/transactions/{uuid}/confirm/` | Manual confirm | `IsAdminUser` |
| POST | `/transactions/{uuid}/release/` | Release | `IsAdminUser` |
| POST | `/transactions/{uuid}/refund/` | Refund | `IsAdminUser` |
| POST | `/transactions/{uuid}/dispute/` | Open dispute | Authenticated + **manual** buyer/admin check |

**Implementation note:** `pay` uses **`self.get_object()`** so the row must be in the **scoped queryset** (buyer/seller/staff).

**`DisputeViewSet`**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/disputes/` | List disputes for parties or staff |
| POST | `/disputes/` | **`create` overridden** — uses `CreateDisputeViaViewSetSerializer` + **`svc.open_dispute`** (no raw ORM dispute create) |

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/disputes/{id}/resolve/` | Admin resolve (`DisputeResolveView`) |

**Webhook:** `POST /webhooks/selcom/` — `AllowAny`; HMAC unless `DEBUG`. Persists `GatewayEvent`, supports async mode.

**Payment links:** Create (auth), detail/OTP/pay (public) with **`EscrowPaymentLinkScopedThrottle`** (per token + IP; rate in `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['escrow_payment_link']`).

**Ops / metrics**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health/` | DB + Redis + Celery worker reachability (`EscrowHealthView`) |
| GET | `/metrics/` | Prometheus text (`prometheus_metrics`) |

**Developer API (nested):** `/api/v1/escrow/dev/` → same router as `/api/v1/transactions/` (see below) **plus** `POST .../dev/keys/rotate/`.

---

### 4.2 Developer API — `/api/v1/transactions/` and `/api/v1/escrow/dev/`

| Component | Behavior |
|-----------|----------|
| **Auth** | `APIKeyAuthentication` — valid **hashed** secret required |
| **Permissions** | `HasEscrowAPIKey` + `EscrowAPIKeyScopes` maps action → scope (`read` / `write` / `pay` / `release` / `refund`) |
| **Throttling** | `EscrowDeveloperAPIKeyThrottle` when `APIKey.rate_limit_per_minute` is set |
| **Queryset** | Transactions / disputes **only** where `transaction.created_by_api_key == request.auth` |

| Action | Scope |
|--------|--------|
| list, retrieve | `read` |
| create transaction, create dispute | `write` |
| pay | `pay` |
| release | `release` |
| refund | `refund` |

**Key rotation:** `POST .../keys/rotate/` — authenticates with current key, returns new secret once, deactivates old key.

---

### 4.3 API review flags (current)

| Flag | Finding |
|------|---------|
| Admin actions | `confirm` / `release` / `refund` use `get_object_or_404(Transaction, pk=...)` — acceptable for **staff-only** endpoints (intentionally global). |
| Developer `CreateTransactionSerializer` | Still exposes **`source`** on the ModelSerializer — a client could send `marketplace` unless validation forbids it; **recommend** forcing `source='api'` in `create()` (as main `TransactionViewSet` does). |
| Webhook + DEBUG | Signature skipped when `DEBUG` — **never** use `DEBUG=True` on internet-facing staging. |
| Async webhooks | When `ESCROW_WEBHOOK_ASYNC=True`, workers must run `process_gateway_webhook_event`. |

---

## 5. Serializers

### 5.1 `serializers.py` (main escrow API)

Includes `TransactionSerializer`, `CreateTransactionSerializer`, payment/dispute serializers, **`CreateDisputeViaViewSetSerializer`** (POST `/disputes/`), **`idempotency_key`** on initiate-payment serializers where applicable.

### 5.2 `api/serializers.py` (developer API)

`TransactionSerializer` exposes **`refunded_at`** (aligned with the model). `CreateTransactionSerializer` is a `ModelSerializer` — see §4.3 for `source` hardening suggestion.

---

## 6. Security review

| Topic | Assessment |
|-------|------------|
| Developer API | **Hashed keys**, scopes, optional IP allowlist, optional per-key rate limit |
| Main API `pay` | Restricted to **transaction buyer** (+ staff object permission path) |
| Webhook | HMAC in production; **idempotent** event store |
| OTP | **No OTP in logs** — only masked phone suffix at INFO |
| Uploads | MIME + size allowlist for dispute counter-evidence |
| Headers | `EscrowSecurityHeadersMiddleware` registered in project settings |
| Residual | Full transaction JSON in responses may include sensitive metadata — review consumers; no AV scan on uploads |

---

## 7. Performance review

| Topic | Finding |
|-------|---------|
| Querysets | `TransactionViewSet` uses **`Q(buyer_user=user) \| Q(seller_user=user)`** (no `union`) + `select_related` / `prefetch_related` |
| Nested serializers | Still risk **N+1** on heavy nested reads if new endpoints omit prefetch |
| Selcom | HTTP calls in request path for initiate/verify — monitor latency |
| Celery | Webhook async path moves work off the web thread |

---

## 8. Transactions and consistency

| Topic | Finding |
|-------|---------|
| Escrow moves | `hold_funds`, `release_funds`, `refund_funds` use **`atomic()`** + **`select_for_update`** on the transaction where implemented |
| Payout | **`PROCESSING`** + distributed lock + second `atomic` block around provider result — reduces double disburse |
| Webhook | Lock + `GatewayEvent` status reduces duplicate confirmation |
| Residual | `release_funds` still logs payout creation failures without rolling back release — operational follow-up may be needed |
| `transition_to` | Still uses direct SQL update + log row; combined with outer `atomic()` in callers |

---

## 9. Integration points

**Dependent / integrated apps:** `commerce`, `marketplace`, `communications`, `insights`, `analytics`, `sellers`, `properties`, websockets/consumers, etc.

**External:** Selcom API, Redis (locks / cache / throttles), Celery.

**Coupling:** Bidirectional **escrow ↔ commerce**; mitigate with documented source-of-truth (`SYSTEM_SOURCE_OF_TRUTH.md` at repo level) and reconciliation tasks.

---

## 10. Background tasks (Celery)

| Task | Purpose |
|------|---------|
| `process_auto_releases` | Release `HOLD` when `auto_release_at` passed — uses **`select_for_update(skip_locked=True)`** per row |
| `process_gateway_webhook_event` | Process stored `GatewayEvent` asynchronously |
| `recover_stuck_payouts` | Fail payouts stuck in **`processing`** past `ESCROW_STUCK_PAYOUT_MINUTES` |
| `release_delivered_marketplace_escrow_periodic` | Auto-release **delivered** orders after window |

**Celery Beat (from `backend/settings.py`):** `release_delivered_marketplace_escrow_periodic` (hourly), `recover_stuck_payouts` (every 15m), plus commerce reconciliation tasks.

**Gap:** **`process_auto_releases` is not registered** in `CELERY_BEAT_SCHEDULE` in settings — if you rely on `auto_release_at`, **add a beat entry** or schedule via `django_celery_beat` admin.

---

## 11. Logging and observability

| Mechanism | Detail |
|-----------|--------|
| Structured logs | `services/metrics_log.py` — `log_escrow_metric` / `log_escrow_failure` |
| Prometheus | Counters/histograms in `prometheus_metrics.py`; scrape via `/api/v1/escrow/metrics/` |
| Health | `/api/v1/escrow/health/` |

---

## 12. Tests and reliability

| File | Focus |
|------|--------|
| `tests/test_production_escrow.py` | `GatewayEvent` idempotency, webhook short-circuit, stuck payout recovery |
| `tests/test_developer_api.py` | API key auth, scoping, scopes |
| `tests/test_services_and_flows.py` | Service-level flows |
| `tests/test_verify_payment_provider.py` | Provider verification behavior |

**Residual:** Expand coverage for **full** permission matrix, **async** webhook path, and **commerce↔escrow** edge cases.

---

## 13. Production readiness score

### **7.5 / 10**

**Rationale:** Strong **hardening pass** is evident: **hashed API keys with scopes**, **buyer-only pay**, **webhook idempotency and locking**, **payout state machine + recovery**, **payment audit records**, **upload validation**, **throttling**, **health/metrics**, and **meaningful tests**. Score is not higher because: **`process_auto_releases` lacks an in-repo Beat schedule**, **delivered auto-release loop** does not use row locks (race possible under concurrency), **developer create** may still accept a client-supplied **`source`**, and **end-to-end / load** testing should be validated in your environment.

---

## 14. Critical issues (must fix before trusting in production)

High impact **remaining** items:

1. **Schedule `process_auto_releases`** (Celery Beat or periodic task) if `auto_release_at` is part of your product contract — otherwise funds may never auto-release on that path.
2. **Force `source='api'`** (or validate allowed values) in Developer API `TransactionViewSet.create` to prevent mis-tagged transactions affecting commerce sync assumptions.
3. **Runbook** for `RELEASED` without payout (logged error today) — ops need a defined retry/reconcile path.

*Previously critical items (insecure dev API key stub, pay IDOR, `models.Q` NameError, OTP in logs, raw Dispute ORM create, wrong disburse amount, `refund_at` typo) are **addressed** in the current tree.*

---

## 15. Suggested improvements

- Add **Beat entry** for `process_auto_releases` + alert on failures.
- Use **`select_for_update`** in `release_delivered_marketplace_escrow_periodic` (or process by primary key list like auto-release).
- Narrow **developer** `CreateTransactionSerializer` fields or override `create` to set immutable fields server-side.
- Move **`DisputeViewSet.respond`** logic into a service; add virus scanning if policy requires.
- Integrate **OpenTelemetry** or trace IDs across webhook → Celery → confirm path.

---

## Appendix A — Transaction status state machine

See `state_machine._TRANSITIONS`. Terminal: `RELEASED`, `REFUNDED`, `FAILED`, `CANCELLED`.

---

## Appendix B — URL mounting (project)

- **`/api/v1/escrow/`** → `escrow_engine.urls` (includes `health/`, `metrics/`, `dev/`)
- **`/api/v1/transactions/`** → `escrow_engine.api.urls` (developer API at top level)

---

*Last updated from a full re-read of `backend/escrow_engine/` and project `settings.py`. Re-audit after changes to auth, webhooks, or payout logic.*
