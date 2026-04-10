# commerce App Documentation

This document describes the **Django `commerce` app** (`backend/commerce/`): domain models, API surface, services, background work, integrations, and a **production-readiness audit**. It is intended for engineers onboarding to the marketplace order flow.

**Base API prefix:** `api/v1/commerce/` (see `backend/backend/urls.py`).

---

## 1. App Overview

### Purpose

The `commerce` app implements **marketplace shopping and order logistics** in the database and HTTP API:

- **Cart** and **wishlist** for buyers.
- **Orders** and **order line items** with pricing snapshots.
- **Stock reservations** to reduce overselling between cart and checkout.
- **Delivery** records (parallel logistics model tied 1:1 to an order).
- **Shipment / dispute evidence** attachments (`OrderEvidence`, order-level `shipment_video`).
- **Commission rules** (`CommissionRule`) used when computing platform fees during checkout (consumption is primarily in `marketplace.services.OrderService`).

Financial **escrow, payouts, disputes, and payment initiation** live in the separate **`escrow_engine`** app. `commerce` integrates with it via `OrderLifecycleManager`, views, serializers (`OrderSerializer.get_escrow`), Celery tasks, and WebSocket consumers.

### Role in the system

| Aspect | Role |
|--------|------|
| Data ownership | Cart, wishlist, order headers/lines, reservations, delivery rows, commission rule config |
| Money movement | Delegated to `escrow_engine` (transactions, holds, releases, refunds) |
| Checkout orchestration | Split: cart checkout and order creation in `marketplace.services.OrderService`; post-order transitions in `commerce.services.lifecycle` |

### Core vs supporting

**Core** for any marketplace purchase path: without it, buyers cannot complete structured multi-seller checkout tied to listings and inventory.

**Supporting** but important: `Delivery`, `OrderEvidence`, `CommissionRule`, WebSocket dashboard fan-out (`consumers.py`, `signals.py`).

---

## 2. Models Audit

All concrete models inherit `core.models.base.BaseModel` (`created_at` with DB index, `updated_at`).

### 2.1 `Cart`

| Field | Type | Purpose |
|-------|------|---------|
| `user` | `OneToOne` → `AUTH_USER_MODEL` | One cart per user (`related_name='cart'`) |

**Indexes / constraints:** Implicit unique on `user_id` (OneToOne).

**Logic:** `@property total` sums `items` subtotals (hits DB per item if not prefetched).

**Signals:** None in `commerce.signals` for `Cart`.

**Audit notes:** No extra DB indexes needed for typical `Cart.objects.filter(user=…)`.

---

### 2.2 `CartItem`

| Field | Type | Purpose |
|-------|------|---------|
| `cart` | `FK` → `Cart`, CASCADE, `related_name='items'` | Parent cart |
| `listing` | `FK` → `listings.Listing`, CASCADE | Product line |
| `quantity` | `PositiveInteger`, `MinValueValidator(1)` | Quantity |
| `price_at_time` | `Decimal(12,2)` | Price snapshot at add/update |

**Constraints:** `unique_together = ('cart', 'listing')`.

**Indexes:** None beyond FK indexes; usually queried as `cart__user` or `cart_id`.

**Signals:** None.

**Audit flags:** Model is thin. **`OrderItem.quantity` has no `MinValueValidator`** (unlike `CartItem`) — validation gap if items are created outside controlled paths.

---

### 2.3 `CommissionRule`

| Field | Type | Purpose |
|-------|------|---------|
| `name` | `CharField(100)` | Label |
| `rule_type` | choices: `percentage`, `fixed`, `hybrid` | Fee structure |
| `percentage_value`, `fixed_value` | `Decimal` | Fee parameters |
| `category` | `FK` → `catalog.Category`, `SET_NULL`, optional | Optional category targeting |
| `is_active` | `bool` | Toggle |
| `priority` | `int` | Higher wins in ordering |

**Meta:** `ordering = ['-priority']`.

**Signals:** None.

**Audit flags (important):** `OrderService.calculate_platform_fee()` loads rules with `CommissionRule.objects.filter(is_active=True).order_by('-priority').first()` **without filtering by `category` (or seller)**. That means **category-specific rules are not reliably applied** unless they happen to be the single highest-priority active rule globally. This is a **business logic / revenue correctness** issue.

---

### 2.4 `Wishlist` / `WishlistItem`

| Model | Key fields | Relationships |
|-------|------------|---------------|
| `Wishlist` | `user` OneToOne | `items` reverse |
| `WishlistItem` | `wishlist` FK, `listing` FK | `unique_together (wishlist, listing)`, `ordering = ['-created_at']` |

**Signals:** None.

**Admin:** **Not registered** in `commerce.admin` (only discoverable via shell or future admin registration).

---

### 2.5 `Order`

| Field | Type | Purpose |
|-------|------|---------|
| `buyer`, `seller` | FK → user | Parties |
| `status` | `CharField`, indexed | Lifecycle (see `STATUS_CHOICES`) |
| `subtotal`, `shipping_cost`, `platform_fee`, `total_amount` | `Decimal` | Money breakdown |
| `currency` | `CharField(3)` default `TZS` | Currency code |
| Shipping | `shipping_address`, `shipping_method`, `tracking_number`, `arrival_location` | Logistics / buyer-facing |
| Notes | `buyer_notes`, `seller_notes`, `admin_notes` | Text |
| Evidence | `shipment_video` `FileField`, `shipment_images_count` | Seller shipment proof |
| Timestamps | `confirmed_at`, `processing_at`, `shipped_at`, `arrived_at`, `delivered_at`, `completed_at`, `cancelled_at` | Audit trail |

**Relationships:**

- `items` → `OrderItem`
- `stock_reservations` → `StockReservation`
- `delivery` → `Delivery` (OneToOne from `Delivery.order`)
- `evidence` → `OrderEvidence`
- **`engine_transaction`** (reverse OneToOne from `escrow_engine.Transaction.linked_order`)

**Indexes (model `Meta.indexes`):**

- `(buyer, status, -created_at)`
- `(seller, status, -created_at)`
- `status` has `db_index=True`

**Constraints / validation:**

- `clean()` enforces a **status state machine** by reloading the old row and comparing transitions.
- `save()` **always calls `clean()`**, so model validation runs on every save (including bulk risk: see §8).

**Methods:** `calculate_subtotal()`, `calculate_total()`, `seller_payout_amount` property.

**Signals:** `pre_save` / `post_save` on `Order` in `commerce.signals` (notifications + WebSocket broadcast).

**Audit flags:**

- **Fat model:** Moderate — state machine + aggregates in model; financial sync is mostly pushed to `OrderLifecycleManager` and `escrow_engine` (good direction).
- **`clean()` uses `Order.objects.get(pk=self.pk)`** — extra read on each update; `pre_save` signal also reads old order → duplicate work.
- **State machine in `clean()` vs admin / management commands:** Anything using `QuerySet.update()` **bypasses** `save()` / `clean()` → **desync risk** with escrow and notifications (see §8).

---

### 2.6 `OrderEvidence`

| Field | Purpose |
|-------|---------|
| `order` FK | Parent order |
| `file` FileField `upload_to='order_evidence/'` | Upload |
| `media_type` image/video | Type hint |
| `caption` | Optional text |

**Admin:** **Not registered** in `commerce.admin`.

**Audit flags:** **No file type/size validation** at model layer; uploads also accepted via API on related endpoints (see §6).

---

### 2.7 `OrderItem`

| Field | Purpose |
|-------|---------|
| `order` FK CASCADE | Parent |
| `listing` FK `SET_NULL` nullable | Survives listing deletion |
| `quantity` | Positive integer (**no MinValueValidator**) |
| `price_at_time` | Snapshot |

**Indexes:** FK defaults only.

---

### 2.8 `StockReservation`

| Field | Purpose |
|-------|---------|
| `listing` FK | Stock owner |
| `order` FK nullable | Set when tied to order |
| `cart_item` FK nullable | Cart-phase reservation |
| `quantity` | Reserved units |
| `status` | `reserved` / `confirmed` / `released` / `expired` (indexed) |
| `expires_at` | TTL (indexed) |

**Indexes:** `(listing, status, expires_at)`, `(status, expires_at)`.

**Methods:** `is_expired()`, `release()` (calls `listing.release_stock`).

**Signals:** None.

**Audit flags:** Reservation / availability math in `InventoryService` and `cart_service` **does not use `select_for_update()`** on listing rows → **race windows** under concurrent checkout (see §7).

---

### 2.9 `Delivery`

| Area | Detail |
|------|--------|
| `order` | OneToOne → `Order`, CASCADE, `related_name='delivery'` |
| `method` | shipping / pickup / digital / local_delivery (indexed) |
| Address block | `address_line1` (required), `address_line2`, city, region, postal, country |
| Tracking | `tracking_number` (indexed), `carrier`, `tracking_url` |
| `status` | Delivery-specific lifecycle (indexed) |
| Timestamps | `shipped_at`, `estimated_delivery`, `delivered_at` |

**Indexes:** `(status, -created_at)`, `(tracking_number)`.

**Serializer:** `DeliverySerializer` exists but **there is no `DeliveryViewSet`** exposed under `commerce.urls` (API gap if clients expect REST CRUD on deliveries).

---

## 3. Business Logic

### Where logic lives

| Layer | Responsibility |
|-------|----------------|
| `marketplace.services.OrderService` | Checkout: group cart by seller, fees, order + delivery creation, stock reserve, **escrow `Transaction` creation**, cart clear, enqueue Celery |
| `marketplace.services.InventoryService` | Reservations, expiry cleanup, stock mutations on listing |
| `commerce.services.cart_service` | Cart get/create, ghost listing cleanup, add-to-cart validation |
| `commerce.services.lifecycle.OrderLifecycleManager` | Order transitions + escrow ops (`hold_funds`, `release_funds`, `refund_funds`, disputes) + `Delivery` sync |
| `commerce.services.stats` | Seller-facing aggregates |
| `commerce.services.review` | Order reviews via `trust` app |
| `commerce.services.registry` | Maps order status → conceptual escrow/delivery statuses (reference registry) |
| `commerce.views` | HTTP orchestration, permission checks, some inline validation |
| `commerce.signals` | Notifications + WebSocket payloads |
| `commerce.tasks` | Email, unpaid cleanup, reservation cleanup, Beat imports `tasks_reconciliation` |
| `commerce.tasks_reconciliation` | Periodic reconciliation scan (`commerce.tasks.reconcile_orders_escrow_periodic`) |
| `escrow_engine.tasks` | Timed escrow release (`release_delivered_marketplace_escrow_periodic`), webhooks, payout recovery |

### Service layer?

**Yes, but split across apps:** primary checkout path is **`marketplace.services`**, not `commerce.services`. `commerce` owns lifecycle after order exists.

### Duplication / coupling

- **Cancellation:** API buyer cancel and **`commerce.tasks.auto_cancel_unpaid_order`** both use **`OrderLifecycleManager.cancel_order`**, which releases stock reservations and calls **`escrow_engine`** refund when the linked transaction is in **PAID / HOLD / DISPUTED**.
- **Status transitions:** Prefer **`OrderLifecycleManager`** (and `order_escrow_sync` after engine-driven money moves). **`Order.save`** blocks direct `status` changes outside authorized contexts; **`OrderQuerySet.update(status=…)`** raises. Admin uses lifecycle actions; **`auto_confirm_orders`** uses **`OrderLifecycleManager.confirm_delivery`**.
- **Tight coupling:** Heavy imports from `escrow_engine`, `marketplace`, `listings`, `trust`, `accounts`, `communications` in views/services/signals/consumers — expected for a marketplace monolith, but not a bounded context.

### Audit flags

- **Business logic in views:** Substantial (checkout, partial updates, dispute evidence file handling, payment return). Prefer thin controllers delegating to services for testability.
- **Scattered rules:** Who may cancel, when disputes open, and payment confirmation paths are split across views + lifecycle + engine.

---

## 4. API Layer (DRF)

**Authentication:** Global DRF settings use `FirebaseAuthentication`, `JWTAuthentication`, and `SessionAuthentication` when `DEBUG` (`backend/backend/settings.py`).

**Default permissions:** Not overridden in this app’s viewsets — **`permissions.IsAuthenticated`** is set explicitly on `CartViewSet`, `OrderViewSet`, and `WishlistViewSet`.

**Rate limiting:** Global **`UserRateThrottle` / `AnonRateThrottle`** apply with project-wide rates (`1000/day` user in non-DEBUG per current settings). **No commerce-specific throttles** (e.g. checkout, payment return).

### 4.1 Registered routes (`commerce/urls.py`)

Router registrations: `cart`, `orders`, `wishlist`.

#### `CartViewSet` (`ModelViewSet`)

| Method / action | Path (relative to `api/v1/commerce/`) | Purpose |
|-----------------|----------------------------------------|---------|
| `list` | `GET cart/` | Returns serialized cart for current user (creates cart via service if needed) |
| Standard `ModelViewSet` | `POST/GET/PUT/PATCH/DELETE cart/…` | **Full CRUD** is enabled unless restricted — creates/updates/deletes carts by pk |
| `add_item` | `POST cart/add_item/` | Add line (`listing_id`, `quantity`) |
| `remove_item` | `POST cart/remove_item/` | Remove by `item_id` |
| `checkout` | `POST cart/checkout/` | Create order(s), optional payment initiation |

**Permissions:** `IsAuthenticated`.

**Audit flags:** **`http_method_names` not restricted** — extra REST surface beyond the custom actions; usually harmless (OneToOne cart) but unnecessary attack surface.

---

#### `OrderViewSet` (`ModelViewSet` with narrowed HTTP verbs)

`http_method_names = ['get', 'post', 'patch', 'head', 'options']` — **no DELETE**.

| Method / action | Path | Purpose |
|-----------------|------|---------|
| `list` | `GET orders/` | Buyer/seller scoped lists; `?role=seller|buyer`; `?status=`; `?include_unpaid=` for staff |
| `retrieve` | `GET orders/{id}/` | Strict object-level buyer/seller/staff check |
| `partial_update` | `PATCH orders/{id}/` | Buyer cancel; seller/admin field updates |
| `create` | `POST orders/` | **Inherited `ModelViewSet.create` — not overridden** |
| `ship_order` | `POST orders/{id}/ship_order/` | Seller shipment + files |
| `open_dispute` | `POST orders/{id}/open_dispute/` | Buyer dispute + evidence files |
| `resolve_dispute` | `POST orders/{id}/resolve_dispute/` | Staff resolution |
| `confirm_receipt` | `POST orders/{id}/confirm_receipt/` | Buyer receipt → lifecycle (completes + release) |
| `initiate_order_payment` | `POST orders/{id}/initiate-payment/` | Hosted checkout retry |
| `confirm_payment_return` | `POST orders/confirm-payment-return/` | Client-side payment confirmation fallback |
| `review` | `POST orders/{id}/review/` | Create trust review |
| `seller_stats` | `GET orders/seller_stats/` | Aggregated seller metrics |
| `seller_escrow` | `GET orders/seller_escrow/` | Last 50 engine transactions for seller |
| `process` | `POST orders/{id}/process/` | Docstring: admin payout processing |
| `payouts` | `GET orders/payouts/` | Seller payout list |

**Query optimizations:** `select_related('buyer','seller','engine_transaction')`, `prefetch_related('items__listing__media')`.

**Audit flags:**

- **`create` (POST collection) is exposed** — serializer marks `buyer`/`seller` read-only, so naive creates will typically **fail DB constraints**, but the endpoint is still **confusing, untested, and risky if serializer fields change**.
- **`process` action:** Uses `self.get_object()` (an **`Order`**) and passes it to `process_seller_payout` from `escrow_engine` — **wrong model type** for a payout processor. **Broken and dangerous** if it ever runs without immediate exception.
- **`review` action:** Calls `create_order_review(order, user, …)` but **`order` and `user` are undefined** in the method body → **`NameError` at runtime** (feature completely broken).

---

#### `WishlistViewSet` (`ViewSet`)

| Action | Path | Purpose |
|--------|------|---------|
| `list` | `GET wishlist/` | Wishlist + items |
| `add` | `POST wishlist/add/` | `listing_id` |
| `remove` | `POST wishlist/remove/` | `wishlist_item_id` or `item_id` |
| `toggle` | `POST wishlist/toggle/` | Add or remove |

**Permissions:** `IsAuthenticated`.

---

### 4.2 Permission class gaps

- Most sensitive actions implement **manual checks** (`buyer == user`, `seller == user`, staff flags) instead of dedicated DRF permission classes (`IsAdmin` is imported in `views.py` but **not applied** to dispute resolution — staff check is inline).
- **No object-level permission backend** — consistency relies on `get_object()` and per-action guards.

### 4.3 Overexposed / unusual endpoints

- **`confirm_payment_return`:** Intended as webhook fallback; **trust implications** are severe (see §6).
- **`seller_escrow`:** Returns financial summaries to authenticated users meeting seller heuristic — OK if role checks are correct; still sensitive data.

---

## 5. Serializers

| Serializer | Purpose |
|------------|---------|
| `CartItemSerializer` | Nested cart lines + `ListingSerializer` |
| `CartSerializer` | Cart + `item_count` (`items.count()` per serialization) |
| `OrderItemSerializer` | Order lines; `listing_id` write-only (mostly unused in current API flow) |
| `OrderEvidenceSerializer` | Evidence + `file_url` |
| `OrderSerializer` | Large read shape for dashboards: nested users, items, escrow snapshot, buyer/seller detail dicts, legacy aliases (`orderNumber`, `totalAmount`, …) |
| `DeliverySerializer` | Delivery + nested `OrderSerializer` (**heavy if used in lists**) |
| `StockReservationSerializer` | Not wired to a public viewset in `commerce.urls` |
| `WishlistItemSerializer` / `WishlistSerializer` | Wishlist API |

### Validation

- **Cart / wishlist:** Mostly validated in views (required IDs) not serializer `validate_*`.
- **OrderSerializer:** `status` is a plain `CharField` **not** in `read_only_fields` — dangerous if `OrderSerializer` is ever used for untrusted writes.
- **Nested `UserSerializer` / `ListingSerializer`:** Rich **PII exposure** (emails, phones, addresses) on order payloads — intentional for seller/buyer dashboards but high sensitivity.

### Audit flags

- **OrderSerializer** is **large** and does many `obj.items.exists()` / `obj.items.first()` / `obj.items.all()` — N+1 risk if queryset prefetch is missing in any code path.
- **Broad `except Exception: return None` / fallback dicts** in `get_buyer_details` / `get_seller_details` / `get_escrow` — hides data bugs.

---

## 6. Security Review

| Topic | Finding |
|-------|---------|
| Authentication | Relies on project defaults; all commerce viewsets require login. |
| **Payment confirmation** | `confirm_payment_return` defaults `gateway_status` to **`SUCCESS`** when omitted. `escrow_engine.services.payment.confirm_payment` **does not verify** the gateway — it transitions to **PAID** and **holds** funds. A buyer who can guess or obtain a `transaction_reference` could **mark unpaid transactions paid** unless additional controls exist upstream. **High impact.** |
| **File uploads** | `shipment_video`, `shipment_images`, dispute evidence: **no explicit content-type/size restrictions** in commerce views. |
| **PII** | Order API returns buyer/seller emails, phones, addresses to counterparties — by design for marketplace, but must be **policy-aligned** (GDPR/consent, data minimization). |
| **Staff actions** | Dispute resolution checks `is_staff` / `is_superuser` inline — OK pattern, but easy to regress without tests. |
| **Rate limiting** | Only global DRF throttles; **no tightened limits** on checkout / payment / dispute endpoints. |
| **Audit trail** | No dedicated **audit log model** in `commerce` for money-adjacent actions (who released/refunded, IP, payload hash). Relies on engine + Django admin. |

---

## 7. Performance Review

| Issue | Detail |
|-------|--------|
| **N+1** | `OrderSerializer` methods hit `items` repeatedly; mitigated in `get_queryset` for list/retrieve, **not automatically** for all code paths (signals, WebSocket). |
| **Signals** | `post_save` builds full `OrderSerializer` and broadcasts to Channels — **expensive on every save**. |
| **CartSerializer.get_item_count** | `obj.items.count()` per request. |
| **`cart_service.remove_ghost_items`** | Loops cart items with `refresh_from_db()` per row. |
| **Stock / listing races** | No row-level locking on listing stock during reserve/checkout. |
| **Periodic unpaid scan** | `check_unpaid_orders_periodic` loops orders and `.delay()` per row — OK at small scale; could batch. |
| **Consumer stats** | `commerce.consumers` aggregates for dashboards; errors are swallowed into `{}` in places — can hide ORM issues (e.g. complex aggregates). |

**Indexes:** Order and reservation indexes are reasonable for buyer/seller dashboards; consider query patterns on `engine_transaction` joins (handled in queryset).

---

## 8. Transactions & Consistency

| Area | Assessment |
|------|------------|
| Checkout | `CartViewSet.checkout` wraps `OrderService.create_order_from_cart` in **`transaction.atomic()`** when gateway path is used; `OrderService.create_order_from_cart` is also `@transaction.atomic`. |
| Lifecycle | `OrderLifecycleManager` methods use **`@transaction.atomic`** per operation. |
| **Race conditions** | Concurrent purchases of last unit: reservation math can overlap without **`select_for_update`**. |
| **Order vs escrow** | Designed to sync via lifecycle + engine services; **admin `update()` actions** and **management `auto_confirm_orders`** bypass model `clean()` and lifecycle → **invariant risk**. |
| **`auto_confirm_orders`** | Uses raw `update` to set `delivered` only; **does not** run `OrderLifecycleManager` — **no automatic escrow release** from this command; help text says “confirm receipt” but behavior is “mark delivered”. |

---

## 9. Integration Points

### Apps that depend on `commerce`

Including direct imports:

- **`escrow_engine`** — `Order` link, status sync helpers.
- **`marketplace`** — `OrderService`, `InventoryService`, seller/store stats.
- **`communications`** — notifications tied to orders; Channels routing includes `commerce.consumers`.
- **`insights`**, **`analytics`** — reporting.
- **`accounts`** — references `Order` in views.
- **`trust`** — reviews after release.

### External services

- **Payment providers** (via `escrow_engine`): Selcom / registry-driven initiation from checkout and order payment action.
- **Email:** `send_mail` in Celery task.
- **Push / notifications:** `communications.notification_service`.
- **WebSockets:** Django Channels layer for dashboard groups.

### Circular dependencies

Lazy imports are used in places (`trust`, `catalog` inside commands). No hard circular import failure observed in static review, but **conceptual coupling** to `escrow_engine` is strong.

---

## 10. Background Tasks (Celery)

| Task | Role | Retries |
|------|------|---------|
| `send_order_confirmation_email` | Email buyer | `max_retries=3`, `autoretry_for`, backoff |
| `auto_cancel_unpaid_order` | Cancel stale pending orders | Same |
| `check_unpaid_orders_periodic` | Beat: enqueue cancels | No retry on outer task |
| `check_escrow_release_periodic` | Auto `release_funds` for old delivered + HOLD | Logs per failure |
| `cleanup_expired_reservations_periodic` | Inventory cleanup | Logs errors |
| `core.tasks.dispatch_event_task` | Domain event side effects (`ORDER_COMPLETED`, `PAYMENT_CONFIRMED`, …) via `core.event_handlers` | `max_retries=3`, `autoretry_for`, backoff |

Lifecycle and checkout call **`core.events.emit_event`** (also re-exported as **`commerce.services.events.emit_event`**), which logs at INFO and enqueues the task above. **Money and order state** still change only through synchronous services (`OrderLifecycleManager`, `escrow_engine`); handlers must stay side-effect-only.

**Assessment:** Email and single-order cancel tasks have **retry**; periodic wrappers are thin. **Missing:** explicit **idempotency** documentation for `auto_cancel_unpaid_order` if run twice; **engine transaction cancellation** not aligned (see §3).

---

## 11. Logging & Observability

- Views and tasks use **`logging.getLogger(__name__)`** — good baseline.
- **No `print()`** statements found under `backend/commerce/`.
- **Sentry** hooks exist at project level (`settings.py`) — commerce benefits indirectly.
- **Payment return** logs exceptions on failure path.
- **Domain events:** `[EVENT] …` at INFO from **`emit_event`**; async follow-up in **`core.tasks.dispatch_event_task`** / **`core.event_handlers`** (see §10). Payloads are normalized for Celery JSON serialization.

**Gaps:** No structured **audit** for dispute resolution / manual status edits; WebSocket failures only `warning` in signals.

---

## 12. Tests & Reliability

- **No dedicated `commerce` test module** was found under `backend/commerce/`.
- **Minimal cross-app usage:** `accounts/tests_redirect.py` imports `Order`.

**Gaps (high value to add):**

- Checkout + rollback on failed payment initiation.
- Permission matrix on `OrderViewSet` (`get_object`, `partial_update`, each `@action`).
- **`review` and `process` actions** (currently broken / unsafe).
- Stock reservation concurrency (even a simple two-thread or transactional test).
- **`confirm_payment_return`** abuse cases.

---

## 13. Production Readiness Score

**Score: 4 / 10**

**Why:** The app has a clear domain model, indexed hot paths, a dedicated lifecycle service, and integrates with a separate escrow engine — all positive. However, **verified defects** in the order API (`review`, `process`), **payment-return trust model**, **commission rule selection ignoring category**, **divergent cancellation paths** (buyer vs Celery), **bypass of lifecycle in admin/commands**, **race-prone inventory**, and **absence of focused automated tests** make shipping this as-is to production **high risk** for money, data integrity, and support load.

---

## 14. Critical Issues (MUST FIX)

Only **high-impact** items:

1. **`OrderViewSet.review` — runtime failure:** Uses undefined `order` and `user` → **`NameError`**; reviews cannot work.
2. **`OrderViewSet.process` — wrong domain object:** Passes an **`Order`** instance into **`process_seller_payout`** (expects a **`Payout`** / engine object) — **broken**; fix or remove before any operator uses it.
3. **`confirm_payment_return` + `confirm_payment` trust model:** Client-supplied success (default **SUCCESS**) can **confirm payments without cryptographic gateway verification** — **fraud / financial loss risk**. Require verified gateway callback, HMAC, or server-side status poll; never default to success.
4. **`OrderService.calculate_platform_fee` ignores `CommissionRule.category`:** Category rules in DB **do not apply** as documented — **incorrect fees** and potential legal/commercial disputes.
5. **Unpaid order auto-cancel uses `OrderService.cancel_order`:** Does **not** mirror **`OrderLifecycleManager.cancel_order`** escrow handling; risks **orphaned or mismatched engine transactions** vs marketplace order state (severity depends on txn state, but operationally dangerous at scale).
6. **Inventory reservation without row locks:** **Overselling** possible under concurrency without `select_for_update` (or equivalent).

---

## 15. Suggested Improvements

### Refactoring

- Remove or lock down **`ModelViewSet.create`** on `OrderViewSet` (explicit `http_method_names` without `post` on collection, or override `create` to `405`).
- Narrow **`CartViewSet`** HTTP methods to what the product needs.
- Move **`partial_update`** status/timestamp logic fully into **`OrderLifecycleManager`** so one path updates time fields + escrow side effects.
- Register **`Wishlist`** / **`OrderEvidence`** in admin if operators need visibility.

### Performance

- In **`OrderSerializer`**, prefer annotated/prefetched data for item counts and first listing instead of repeated queries.
- Debounce or slim **WebSocket payloads** (send ids + changed fields, not full `OrderSerializer` every time).
- Replace `remove_ghost_items` row loop with queryset-based deletion where possible.

### Security

- Add **upload validators** (max size, allowed MIME, virus scan hook if required).
- Add **commerce-scoped throttles** on `checkout`, `initiate-payment`, `confirm-payment-return`, `open_dispute`.
- Implement **immutable audit log** entries for payout/dispute/status changes.

### Architecture

- Single **“cancel order”** service used by API, Celery, and admin (or admin calls the same service).
- Apply **commission rules** with explicit precedence: match `category` / seller tier, then fallback global rule.
- Document **canonical order state machine** and enforce via one module (reject raw `update()` in admin or reimplement as service calls).

---

## Appendix A — Signals (`commerce.signals`)

| Signal | Handler | Behavior |
|--------|---------|----------|
| `pre_save` `Order` | `fetch_previous_status` | Stashes `_old_status` for transition detection |
| `post_save` `Order` | `handle_order_status_notifications` | Push notifications on create / status change; WebSocket `order_update` to admin, seller, buyer groups |

**Risk:** Side effects on every save; failures in notification/WebSocket are partially swallowed (WS wrapped in `try/except` with `logger.warning`).

---

## Appendix B — Management commands

| Command | Purpose |
|---------|---------|
| `setup_commission_rules` | Bootstrap `CommissionRule` rows (optional `--reset`) |
| `auto_confirm_orders` | Bulk `update` orders to `delivered` after N days — **does not run lifecycle / escrow release**; naming vs behavior should be reconciled |

---

*Document generated from static analysis of `backend/commerce/` and related project code. Re-run this audit after major refactors or before release.*
