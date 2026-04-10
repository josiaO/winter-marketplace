# Marketplace App Documentation

**Django app path:** `backend/marketplace/`  
**API mount:** `https://<host>/api/v1/marketplace/` (see `backend/backend/urls.py`)

This document is a **production-readiness audit** and **developer reference** for the `marketplace` Django application. It was produced by reading the codebase (models, views, serializers, services, signals, tasks, URLs, tests, and cross-app imports)—not by assumption.

---

## 1. App overview

### Purpose

The **marketplace** app models and exposes:

- **Marketplace products** as `MarketplaceItem` (multi-table inheritance from `listings.Listing`): leaf-category validation, storefront linkage, and product-specific attribute rows.
- **Seller identity and storefront**: `SellerProfile`, `Store`, `StoreFollow`, seller payout identifiers via `SellerPaymentMethod`.
- **Supporting data**: `ProductAttributeValue` (normalized dynamic attributes), `ProductModerationLog` (automated image moderation audit).
- **Heavy commerce orchestration** in `marketplace/services.py`: stock reservations, order creation from cart, platform fee calculation, escrow transaction creation—used heavily by the **commerce** app.

### Role in the system

| Concern | Role of this app |
|--------|-------------------|
| Product catalog (DB) | Extends shared `Listing` model; same row as `listings_listing` with extra `marketplace_marketplaceitem` row. |
| Seller onboarding surface | `SellerProfile` / `Store` are referenced from **sellers**, **accounts**, **trust**, **insights**, **commerce** (WebSocket consumer), etc. |
| Checkout & money flow | `OrderService` / `InventoryService` are **core** dependencies for cart → order → `escrow_engine` transaction creation. |
| Search | `post_save` on `MarketplaceItem` queues Typesense sync (`tasks.sync_product_to_typesense`). |
| Payout routing | `post_save` on `SellerPaymentMethod` syncs `escrow_engine.PayoutDestination`. |

### Core vs supporting

- **Core** for any product-selling flow: `MarketplaceItem`, `SellerProfile`, `Store`, services used by commerce (`OrderService`, `InventoryService`), and payment-method → payout sync.
- **Supporting**: moderation logs, favorites API wrappers, management commands, verification scripts.

The platform can exist without marketplace **only** if no internal product checkout or seller storefront features are required; in this codebase, **commerce** and **escrow_engine** are already integrated with marketplace concepts.

---

## 2. Models audit

Below, **PK** = primary key, **FK** = foreign key, **O2O** = one-to-one, **M2M** = many-to-many.

### 2.1 `MarketplaceItem` (`marketplace.MarketplaceItem`)

| Aspect | Detail |
|--------|--------|
| **Inheritance** | Child of `listings.Listing` (MTI). Parent holds title, price, stock, publish flags, owner, store, category, media, etc. |
| **Extra fields** | None on the child table in code—behavior is `clean()` / `save()` for **leaf category** enforcement. |
| **Relationships** | Implicit: same as `Listing` (owner → `AUTH_USER_MODEL`, store → `Store`, category → `catalog.Category`, …). |
| **Indexes** | `Meta.indexes = []` by design; parent `Listing` / `BaseListing` carry query indexes. |
| **Constraints / validation** | `clean()`: category must be a **leaf** (`category.is_leaf()`). `save()` calls `full_clean()`—always validates on save. |
| **Signals** | `post_save` → `sync_product_on_save` queues `sync_product_to_typesense.delay` (`signals.py`). |
| **Fat model?** | **No**—thin; domain rules are minimal. |
| **Missing validation** | Leaf category enforced; broader listing validation lives on parent / serializers. |
| **Risks** | `full_clean()` on every save can add cost on bulk updates; acceptable for typical write volume but worth monitoring. |

### 2.2 `SellerProfile` (`marketplace.SellerProfile`)

| Field group | Purpose |
|-------------|---------|
| `user` (O2O → User) | One profile per user. |
| Business | `business_name`, `business_type`, `tax_id`, phones, email, address. |
| Verification | `is_verified`, `verified_at`, `verification_documents` (JSON list of URLs), `verification_status` (structured onboarding states). |
| Storefront | `store_name`, `store_categories` (JSON), `store_category` (legacy), `store_logo`, `store_location`, `store_description`, notification toggles, shipping/return policy. |
| Denormalized stats | `average_rating`, `total_reviews`, `total_sales`, `completed_orders`. |
| Limits | `products_limit`, `payout_limit`. |
| Status | `is_active`, `suspended_at`, `suspension_reason`, `is_business_verified`. |

| Aspect | Detail |
|--------|--------|
| **Indexes** | Per-field `db_index` on several flags; composite indexes `(is_verified, is_active)`, `(average_rating, -completed_orders)`. |
| **Constraints** | `UniqueConstraint` on `store_name` when non-empty (`uniq_sellerprofile_store_name_when_set`). |
| **`save()` logic** | If `verification_status != 'verified'`, forces **`is_active = False`**. Normalizes `store_categories` ↔ `store_category`. |
| **Signals** | None on this model in `marketplace/signals.py` (other apps may react). |
| **`update_ratings()`** | Delegates to `SellerService.update_seller_ratings`. |

**Flags**

- **Dual verification model**: `is_verified` (legacy/admin) vs `verification_status` (onboarding). `save()` only gates **`is_active`** on `verification_status`, not `is_verified`. Admin/API actions that set `is_verified` without setting `verification_status='verified'` **do not activate** the seller storefront—high confusion and support risk (see §14).
- **JSON `verification_documents`**: URLs stored; access control depends on storage backend and who can read profile payloads (see §6).

### 2.3 `Store` (`marketplace.Store`)

| Field | Purpose |
|-------|---------|
| `seller` (FK → `SellerProfile`) | Owner. |
| `name`, `slug` (unique) | Public identity; `slug` used in URLs (`StoreViewSet.lookup_field`). |
| Branding | `logo`, `banner` (`ImageField`). |
| `is_active`, `is_featured` | Visibility / merchandising. |
| Contact / social | Email, phone, website, `social_links` JSON. |
| Denormalized | `total_listings`, `total_sales`, `total_followers`. |

| Aspect | Detail |
|--------|--------|
| **Indexes** | `(seller, is_active)`, `(is_featured, -total_sales)`, plus single-field indexes on `name`, `slug`, flags. |
| **`update_statistics()`** | Delegates to `SellerService.update_store_statistics`. |

### 2.4 `StoreFollow` (`marketplace.StoreFollow`)

| Aspect | Detail |
|--------|--------|
| **Fields** | `user` (FK), `store` (FK). |
| **Constraints** | `unique_together` (`user`, `store`). |
| **Indexes** | Implicit on FKs; no extra composite beyond uniqueness. |

### 2.5 `ProductAttributeValue` (`marketplace.ProductAttributeValue`)

| Aspect | Detail |
|--------|--------|
| **Purpose** | One row per (product, attribute) for typed values (`value_text`, `value_number`, `value_boolean`, `value_option`). |
| **Relationships** | FK → `MarketplaceItem`, `catalog.Attribute`, optional `catalog.AttributeOption`. |
| **Constraints** | `unique_together` (`product`, `attribute`). |
| **`get_value()`** | Dispatches by `attribute.field_type`. |

**Flags**

- No model-level validation that the value type matches `field_type`—serializer / `_save_attribute_values` logic must stay correct.

### 2.6 `ProductModerationLog` (`marketplace.ProductModerationLog`)

| Aspect | Detail |
|--------|--------|
| **Purpose** | Audit trail for Google Vision SafeSearch runs. |
| **Fields** | `product` (FK), `image_url`, `is_safe`, `unsafe_reasons`, `safe_search_result`, `moderated_at`. |
| **Indexes** | `moderated_at`, `is_safe` indexed. |

### 2.7 `SellerPaymentMethod` (`marketplace.SellerPaymentMethod`)

| Aspect | Detail |
|--------|--------|
| **Purpose** | Seller payout identifiers (mobile money, bank, card labels, till). |
| **Relationships** | FK → `SellerProfile`. |
| **Signals** | `post_save` → sync to `escrow_engine.models.payout.PayoutDestination` (`update_or_create` by user + method + account_number). |

**Flags**

- **Sensitive data** (`account_number`, `account_name`) exposed through API serializer—must rely on permissions (see §4).

---

## 3. Business logic

### Where logic lives

| Layer | Responsibility |
|-------|----------------|
| **`marketplace/services.py`** | `InventoryService`, `OrderService`, `PriceAnomalyService`, `SellerService`; helpers `ensure_default_store_for_seller`, `sync_store_from_seller_profile`, `validate_attributes` / `normalize_specs`. |
| **`marketplace/services/seller_service.py`** | Document uploads to storage, seller review aggregates, `toggle_store_follow` (atomic + follower count). |
| **`marketplace/publish_guards.py`** | Identity checks before `is_published` becomes true (settings-driven). |
| **`marketplace/serializers.py`** | Store assignment, publish rules, attribute persistence from `specs`, nested read serializers. |
| **`marketplace/views.py`** | Permission branching, queryset filtering (ghost listings), favorites endpoints, thin orchestration for some seller actions. |
| **`marketplace/models.py`** | `SellerProfile.save`, `MarketplaceItem.clean/save`, delegating methods on profile/store. |

### Service layer?

**Yes**, but **split across two modules** (`services.py` and `services/seller_service.py`) plus substantial logic in **serializers** and **parent listing** code (`core.models.listing` for `is_ghost_listing`, `get_similar_listings`).

### Duplication / coupling

- **Tight coupling** to **commerce** (`Order`, `OrderItem`, `StockReservation`, `Delivery`, `CommissionRule`, `OrderLifecycleManager`), **escrow_engine** (create transaction), **trust** (reviews, price anomalies), **catalog** (attributes), **listings** (base listing, likes).
- **`validate_listing_attributes` / `validate_attributes` / `normalize_specs`** in `services.py` are **not wired** from `MarketplaceItemSerializer`—category schema validation is effectively **unused** in the main API path (only `publish_guards` + store/seller checks run in `validate()`).
- **Order lifecycle** split: marketplace creates orders; **commerce** owns confirmation, payment return, reconciliation—documented elsewhere but important for ops.

### Flags

- **Logic in views**: `SellerProfileViewSet.verify` / `unverify` embed state changes without a dedicated service (and without aligning `verification_status`).
- **Logic in serializers**: `MarketplaceItemSerializer.validate`, `_save_attribute_values`, `SellerProfileSerializer.update` (sync store)—acceptable but dense.
- **Scattered files**: seller document upload in `seller_service`, reviews stats there too, while ratings update is in `SellerService`.

---

## 4. API layer (DRF)

**Router** (`marketplace/urls.py`): included under `/api/v1/marketplace/`.

| Resource | ViewSet / view | Typical paths | List/retrieve auth | Write auth |
|----------|----------------|---------------|-------------------|------------|
| Marketplace items | `MarketplaceItemViewSet` | `items/`, `items/{id}/` | `AllowAny` | `IsAuthenticated` + `(IsAgent \| IsSeller)` |
| Seller profiles | `SellerProfileViewSet` | `sellers/`, `sellers/{id}/` | `AllowAny` | `IsAuthenticated` (create/update); `verify`/`unverify` → `IsAdminUser` |
| Stores | `StoreViewSet` | `stores/`, `stores/{slug}/` | `AllowAny` | `IsAuthenticated` |
| Payment methods | `SellerPaymentMethodViewSet` | `payment-methods/`, `payment-methods/{id}/` | N/A (all actions authenticated) | `IsAuthenticated` + `IsSeller` |
| Favorites | `favorites_list_add` | `favorites/` GET/POST | — | `IsAuthenticated` |
| Favorites | `favorites_remove` | `favorites/{favorite_id}/` DELETE | — | `IsAuthenticated` |

### Per-endpoint behavior (summary)

| Endpoint | Method | Behavior |
|----------|--------|----------|
| `items/` | GET | Paginated marketplace items: published, non-ghost (active owner, active/null seller profile, active/null store). Supports filters (`category`, `status`, `listing_type`, `condition`, `city`), search, ordering. |
| `items/` | POST | Create listing; `owner` set to current user. |
| `items/{id}/` | GET | Owner can see draft; others only if “public_ok” (published + non-ghost). |
| `items/{id}/` | PATCH/PUT/DELETE | Authenticated agent/seller; object-level enforcement via queryset + typical DRF ownership expectations. |
| `sellers/` | GET | Non-staff: verified sellers only, plus own profile if logged in. Staff: broader access (see queryset). |
| `sellers/` | POST | Create profile for `request.user` if none exists. |
| `sellers/{id}/` | GET | **Queryset not restricted for `retrieve` for non-staff**—see §6 / §14. |
| `sellers/{id}/` | PATCH | Non-staff queryset limited to own profile. |
| `sellers/{id}/verify/` | POST | Sets `is_verified=True`, `verified_at=now` (admin). |
| `sellers/{id}/unverify/` | POST | Clears verification flags (admin). |
| `sellers/{id}/upload_documents/` | POST | Multipart `documents`; calls seller document handler. |
| `sellers/{id}/reviews/` | GET | Public; returns stats + paginated `ReviewSerializer` data. |
| `stores/` | GET | Active stores (`queryset` base filter). |
| `stores/{slug}/` | GET | Retrieve by slug. |
| `stores/` | POST | Create store for current user’s `SellerProfile`. |
| `stores/{slug}/follow/` | POST | Toggle follow on (`IsAuthenticated` from `get_permissions` for non-safe actions). |
| `stores/{slug}/unfollow/` | POST | Toggle follow off. |
| `payment-methods/` | CRUD | Scoped to `seller__user=request.user`. |
| `favorites/` | GET | Lists current user’s `ListingLike` where listing published. |
| `favorites/` | POST | Body: `listingId` or `listing`; creates like. |
| `favorites/{id}/` | DELETE | By like PK or listing id. |

### Authentication

Uses project defaults (`backend/settings.py`): Firebase, JWT, optional session in `DEBUG`.

### Permissions review

- **`IsSeller` / `IsAgent`**: In `core/permissions.py`, `IsAgent` is an **alias of `IsSeller`**—naming is misleading for API docs.
- **Staff vs admin**: `verify`/`unverify` use `IsAdminUser` (often **superuser** in Django), not custom `IsAdmin`—may be stricter or looser than product intent.
- **Payment methods**: Correctly scoped queryset; good pattern.

### Rate limiting

Project-wide `DEFAULT_THROTTLE_CLASSES` (`AnonRateThrottle`, `UserRateThrottle`) apply unless overridden. Marketplace viewsets do **not** define scoped throttles (contrast with commerce checkout rates in settings). Production anon/user caps are **100/day** and **1000/day** respectively when `DEBUG` is false—verify these align with product needs.

### Flags

- **Missing object-level permission class** for seller profile **retrieve** (see §6).
- **Overexposure** of seller profile and payment method fields via serializers (see §6).
- **No endpoint-specific throttles** for write-heavy paths (listing create, document upload).

---

## 5. Serializers

| Serializer | Purpose |
|------------|---------|
| `ProductAttributeValueSerializer` | Read-oriented attribute display with `get_value()`. |
| `MarketplaceItemSerializer` | CRUD for marketplace items; nested media; `specs` → `ProductAttributeValue` rows; publish/store/seller validation; `similar_listings` / ghost handling. |
| `SellerPaymentMethodSerializer` | CRUD for payout methods; exposes provider display name. |
| `SellerProfileSerializer` | Profile read/update; nested `UserSerializer`, read-only `payment_methods`; `store_categories` validation; `update` calls `sync_store_from_seller_profile` (errors **swallowed**). |
| `StoreSerializer` | Store CRUD/read; nested **full** `SellerProfileSerializer` on read; `is_followed` uses per-object `StoreFollow.objects.filter(...).exists()`. |
| `StoreFollowSerializer` | Defined; **not registered** on a viewset in this app’s `urls.py`. |

### Validation

- **MarketplaceItem**: Strong checks for seller profile, active store, store ownership, publish identity rules (`publish_guards`).
- **SellerProfile**: Store name uniqueness (case-insensitive), “other” category text required when applicable.
- **SellerPaymentMethod**: Standard model fields—no extra normalization of phone/account formats in serializer.

### Nested serializers

- **Store → SellerProfile → User + payment_methods**: Large payloads; risk of **over-fetch** and **N+1** if queryset not optimized (store list uses `select_related('seller', 'seller__user')` but not `prefetch_related('seller__payment_methods')`).

### Flags

- **Business logic in serializers**: `MarketplaceItemSerializer._save_attribute_values` (DB writes), `SellerProfileSerializer.update` (sync store)—keep changes carefully reviewed.
- **`SellerProfileSerializer.update`**: `except Exception: pass` around `sync_store_from_seller_profile` **hides failures**—operational risk.
- **`StoreSerializer`**: `slug` is **read-only**; API create must still supply a unique slug at DB level—**no `create()` override** to generate slug (likely **broken or unused** for API-created stores unless another layer sets it)—see §14.

---

## 6. Security review

| Topic | Finding |
|-------|---------|
| **Authentication** | Relies on global DRF auth; no marketplace-specific gaps in code beyond missing checks below. |
| **Seller profile retrieve** | `SellerProfileViewSet.get_queryset()` applies strict filters for `list` and `update`, but **not** for `retrieve`. Any client (including anonymous) with the UUID/ID can fetch **any** seller profile returned by `get_object()`, including **`tax_id`, `business_phone`, `business_email`, `business_address`, `verification_documents`** if present—**critical data exposure**. |
| **Admin verify** | Does not set `verification_status='verified'`; interacts badly with `SellerProfile.save()` gating `is_active`—see §14. |
| **Document upload** | `handle_seller_document_upload` saves under `seller_verification/{seller.id}/{file.name}` with **no evident file type/size validation** in this module—risk of oversized uploads, malicious filenames, or unexpected content types (depends on storage and reverse proxy limits). |
| **Payment methods** | Serialized account numbers returned to authenticated seller—expected for “my payout details” but must never be exposed to other users (queryset is correct). |
| **Input validation** | Favorites API accepts raw listing id; checks `is_published=True` only—consistent with public listings. |
| **Rate limiting** | Only global throttles; no dedicated limits for uploads or listing creation. |
| **Audit** | `ProductModerationLog` provides moderation audit; **no general audit log** in this app for seller profile or payment method changes (commerce may cover orders separately). |

---

## 7. Performance review

| Area | Observation |
|------|-------------|
| **MarketplaceItem list** | Good use of `select_related` + `prefetch_related('media', 'likes')`. |
| **Similar listings** | `get_similar_listings` on parent model uses queryset + Python filter; serializer loops results and may hit **per-item media** (`get_similar_listings` in `MarketplaceItemSerializer`)—**N+1** risk on detail responses. |
| **Store list** | Nested seller + `get_is_followed` → **per-store** `exists()` query for authenticated users. |
| **InventoryService** | `cleanup_expired_reservations()` may run during `reserve_stock` and iterates expired rows in Python—could be heavy under backlog (consider periodic task only). |
| **`reserve_stock`** | Sums reservations in Python over querysets; multiple queries per call—acceptable at small scale; watch under high concurrency. |
| **Signals** | Every `MarketplaceItem` save queues Typesense sync—**write amplification**; ensure Celery workers and Typesense handle peak load. |
| **Indexes** | Seller/store models are reasonably indexed; listing indexes live on parent tables. |

---

## 8. Transactions and consistency

| Flow | Transaction usage | Notes |
|------|---------------------|-------|
| `InventoryService.reserve_stock` | `@transaction.atomic` + `select_for_update` on listing | Correct direction for overselling prevention. |
| `OrderService.create_order_from_cart` | `@transaction.atomic` | Groups multi-seller split, reservations, order rows, delivery, escrow txn create, cart clear. |
| `toggle_store_follow` | `@transaction.atomic` | Follow row + follower count update. |
| **Race conditions** | Stock path designed for concurrency; still depends on **all** checkout paths using the same reservation discipline. |
| **Partial failure** | If multiple orders from one cart (multi-seller), failures mid-loop could surface as `ValueError` after some orders created—callers must treat as **critical** (commerce layer should document behavior). |

---

## 9. Integration points

### Apps that depend on marketplace (representative)

- **commerce**: `OrderService`, `InventoryService`, `SellerProfile` in consumers; payment return flows.
- **escrow_engine**: `PayoutDestination` sync; transactions linked to commerce orders created via marketplace services.
- **listings**: `MarketplaceItem`, `MarketplaceItemSerializer`, search service joins.
- **sellers**: `SellerProfile`, `sync_store_from_seller_profile`, signals ensuring default store.
- **trust**: reviews/stats keyed off seller user/profile.
- **insights**, **accounts**, **core**: analytics and account upgrade paths touching `SellerProfile`.
- **search**: Typesense client used from tasks.

### External services

- **Typesense** (product index).
- **Google Cloud Vision** SafeSearch (`moderate_product_image` task).
- **Django file storage** (`default_storage`) for verification uploads and images.

### Coupling / circular dependency risks

- `core.models.listing.BaseListing` imports `marketplace.MarketplaceItem` inside `is_ghost_listing` for edge detection—**runtime import** to reduce circular imports; still a **conceptual coupling** from core → marketplace.
- `listings.serializers` imports `marketplace.publish_guards` for publish rules on listing flows—tight cross-app coordination.

---

## 10. Background tasks (Celery)

| Task | Module | Retries | Purpose |
|------|--------|---------|---------|
| `sync_product_to_typesense` | `tasks.py` | `max_retries=3`, exponential backoff | Upsert product document; no-op if `TYPESENSE_API_KEY` missing. |
| `moderate_product_image` | `tasks.py` | Same | SafeSearch latest image; write `ProductModerationLog`; flag listing + notify staff. |

**Assessment**

- Tasks are **appropriate** for I/O-bound work.
- **Retry logic** is present (`autoretry_for`, backoff).
- **Failure modes**: Missing Vision credentials logs error and returns (no retry improvement); Typesense failures retry.

---

## 11. Logging and observability

| Location | Practice |
|----------|----------|
| `signals.py`, `tasks.py` | Uses `logging.getLogger(__name__)`; info/warning/error used. |
| `seller_service.py` | Logger defined; not verbose on success paths. |
| **Debug prints** | `verify_ghost_listings.py`, `verify_cascading_deletion.py` use `print()`—**scripts only**, not imported by production URLconf; acceptable if run manually. |

**Gaps**

- No structured **correlation id** usage in marketplace modules (project has `CorrelationIdMiddleware`—marketplace could attach it to logs for traceability).
- Swallowed exception in `SellerProfileSerializer.update` prevents observability of store sync failures.

---

## 12. Tests and reliability

| File | Coverage |
|------|----------|
| `tests.py` | **Empty placeholder**—no tests. |
| `tests_publish_guards.py` | **Good unit coverage** for `publish_guards` (transition detection, identity checks, enforcement, settings, staff bypass). |

**Missing (high value)**

- API tests for `MarketplaceItemViewSet` (ghost filtering, owner draft access).
- **Security regression test**: seller profile `retrieve` must not expose unverified/private profiles to strangers.
- `OrderService` / `InventoryService` integration tests live partly under **commerce** (`commerce/tests/test_hardening.py` references marketplace services)—marketplace app itself lacks direct service tests.
- Serializer tests for `_save_attribute_values` edge cases (invalid option, type coercion).

---

## 13. Production readiness score

**Score: 5.5 / 10**

**Why (honest summary)**

- **Strengths**: Real service layer for inventory/orders; transactional stock handling; ghost-listing filtering on public catalog; publish identity gate; Celery tasks with retries; Typesense + moderation hooks; indexed seller/store models; documented MTI relationship with listings.
- **Major deductions**: Verified **runtime bug** (`seller_service` undefined in `views.py`), **seller profile data exposure** on retrieve, **verification field inconsistency** undermining admin flows, likely **store create API / slug gap**, minimal automated tests in the app itself, heavy cross-app coupling without boundary documentation in code, serializer swallowing errors, and performance hotspots (nested serializers, similar listings).

---

## 14. Critical issues (must fix)

These are **high impact** for production go-live:

1. **`marketplace/views.py` references `seller_service` without importing it**  
   Uses: `handle_seller_document_upload`, `get_seller_review_stats`, `toggle_store_follow`. This will raise **`NameError`** when those code paths run (document upload, seller reviews action, store follow/unfollow).

2. **`SellerProfileViewSet` retrieve does not restrict queryset for non-staff users**  
   Unauthenticated or arbitrary users can **read full seller profiles by ID**, including sensitive business and verification document URLs.

3. **`SellerProfile.verify` / admin actions vs `SellerProfile.save()`**  
   `save()` forces `is_active = False` unless `verification_status == 'verified'`. Setting only `is_verified=True` does **not** align with that rule—admins may believe they activated a seller while the profile remains **inactive**.

4. **`StoreSerializer` + `StoreViewSet.create`**  
   `slug` is read-only and there is no serializer `create()` generating a unique slug. Unless **all** stores are created only via `ensure_default_store_for_seller` / admin / scripts, **HTTP POST `/stores/`** is likely **broken** or stores end up with invalid/duplicate slugs.

5. **Verification document uploads lack hardening** in `handle_seller_document_upload` (size, MIME, extension, virus scanning policy)—risk of abuse and storage costs.

---

## 15. Suggested improvements

### Refactoring

- Import and use a single namespace, e.g. `from marketplace.services import seller_service` or `from marketplace.services.seller_service import ...`, and **fix `views.py` immediately**.
- Introduce **`SellerProfileService`** (or extend `SellerService`) for verify/unverify, document upload, and **one** canonical state machine for `verification_status` + `is_verified` + `is_active`.
- Replace bare `except Exception: pass` in `SellerProfileSerializer.update` with logging and/or structured error response on sync failure.
- Consider **`IsAdmin`** from `core.permissions` instead of `IsAdminUser` if staff (not only superuser) should verify sellers.

### Performance

- Prefetch `seller__payment_methods` (and related user) for store list/detail when nested serializer is used.
- Optimize `get_similar_listings` serialization (prefetch media for similar IDs in one query).
- Move `cleanup_expired_reservations` to a **periodic task**; avoid calling it on every hot-path reservation if metrics show contention.

### Security

- **Restrict `retrieve`** on `SellerProfileViewSet` to: own profile, **verified** public profiles, or staff—matching the intent of `list`.
- Add **file upload limits** and allowed content types for verification documents; store in a **non-public** bucket/path if not already enforced at reverse proxy.
- Add **scoped throttles** for `upload_documents`, listing `create`, and favorites mutations.

### Architecture

- Wire **`validate_attributes` / `normalize_specs`** into `MarketplaceItemSerializer` or drop dead code to avoid false confidence.
- Document **ownership rules** for `MarketplaceItem` updates in a small policy module (who may edit: owner only vs agent).
- Reduce **core ↔ marketplace** coupling over time (e.g. move `is_ghost_listing` helpers to a small shared service used by both).

---

## Appendix A: File map

| Path | Role |
|------|------|
| `models.py` | ORM models |
| `views.py` | DRF viewsets + favorites API views |
| `serializers.py` | DRF serializers |
| `urls.py` | Router + favorites paths |
| `services.py` | Inventory, orders, fees, seller/store stats, store sync helpers |
| `services/seller_service.py` | Documents, reviews aggregation, follow toggle |
| `signals.py` | Typesense queue, payout destination sync |
| `tasks.py` | Celery: Typesense, Vision moderation |
| `publish_guards.py` | Publish identity verification |
| `validators.py` / `schemas.py` | Category attribute schemas (partially unused in API) |
| `admin.py` | Django admin registrations |
| `apps.py` | Loads signals in `ready()` |
| `management/commands/generate_marketplace_data.py` | Demo data |
| `verify_*.py` | Manual verification scripts |

---

## Appendix B: Related settings

- `MARKETPLACE_PUBLISH_REQUIRES_IDENTITY_VERIFICATION` (`backend/settings.py`, env-driven, default **true**): blocks publishing until identity verification rules in `publish_guards` pass.

---

*End of Marketplace app documentation and audit.*
