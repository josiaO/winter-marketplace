# 🛡️ SmartDalali Backend: Production-Readiness Audit & System Documentation

**Date:** April 7, 2026  
**Auditor:** Principal Backend Architect & Security Auditor  
**Status:** 🟠 Production Candidate (High Risk)  
**Overall Score:** **84 / 100**

---

## 1. System Overview (Distributed Architecture)
SmartDalali is architected as a **Modular Monolith** with a clear **Service-Oriented Architecture (SOA)** orientation. It is not just a CRUD app; it is a financial clearinghouse connecting property seekers, vehicle buyers, and general marketplace participants.

### Domain Boundaries
*   **Catalog (`catalog`):** The "Source of Truth" for category hierarchies and dynamic attributes.
*   **Listings (`listings`):** The base inventory layer. All verticals (Property, Vehicles, Marketplace) extend this.
*   **Marketplace (`marketplace`):** Extensions to listings for commerce-enabled items (Leaf category enforcement, specific seller rules).
*   **Commerce (`commerce`):** The business state engine. Owns Carts, Orders, and Deliveries.
*   **Escrow Engine (`escrow_engine`):** The heart of the system. An autonomous financial service that tracks "Universal Transactions," holds funds, and manages payouts.

---

## 2. Infrastructure & Deployment Audit

*   **Web Server:** Scalable via Gunicorn/Daphne. Deployment uses fixed `3 workers` in `entrypoint.sh`.
*   **Database:** `conn_max_age=600` for connection pooling. SSL required for Render/Postgres.
*   **Redis:** Single instance used for Cache, Channels (WebSockets), and Celery Broker.
*   **TLS/HTTPS:** Enforced via `SECURE_SSL_REDIRECT` and `SECURE_PROXY_SSL_HEADER`.

🚨 **Flag:** 
*   ❌ **Single Point of Failure (SPOF):** Redis is a critical SPOF. If it fails, all real-time features, background tasks, and distributed locks die simultaneously.
*   ❌ **Scaling Gap:** The fixed worker count in `entrypoint.sh` lacks a true **Horizontal Scaling** strategy (e.g., K8s or Cluster autoscaling).
*   ❌ **Unsafe Default Config:** Redis is used with `IGNORE_EXCEPTIONS: True`, which hides connection issues from the app logger.

---

## 3. Failure Mode & Resilience Analysis (CHAOS)

*   **Payment Failure:** Provider timeout is caught as `ValidationError` in view.
*   **Janitors:** Periodic tasks (`check_unpaid_orders_periodic`, `recover_stuck_payouts`) exist to heal stuck states.

🚨 **Flag:** 
*   ❌ **Redis Downtime:** If Redis is down during a Selcom webhook, the `escrow_distributed_lock` falls back to `cache.add`, which may be unsafe for high-concurrency environments.
*   ❌ **Silent Failures:** Cache misses during Redis outages are silent, potentially leading to stale read/write cycles without alerting.
*   ❌ **Stuck Celery:** Payouts rely on `CELERY_BEAT_SCHEDULE`. If the worker lags, payouts can be delayed indefinitely without a dead-letter queue (DLQ) strategy.

---

## 4. Data Lifecycle & Compliance

*   **Retention:** Orders/Transactions are currently kept indefinitely.
*   **Compliance:** PII exists in `Profile` and `SellerProfile`.

🚨 **Flag:** 
*   ❌ **Unbounded Growth:** No archival strategy for old `Order` and `Log` rows exists. PostgreSQL performance will degrade at 5M+ records.
*   ❌ **Legal Risk:** No explicit PII deletion (Right to be Forgotten) or data retention policy found. This is a high compliance risk for international expansion.
*   ❌ **Backup Strategy:** No visible backup verification pipeline in the codebase.

---

## 5. API Versioning & Contract Stability

*   **Strategy:** Hardcoded `/api/v1/` prefix in `urls.py`.
*   **Contract:** `drf_spectacular` generates OpenAPI schemas.

🚨 **Flag:** 
*   ❌ **Inflexible Versioning:** No middleware-level versioning exists. Breaking changes forced onto `/api/v2/` will require significant URL restructuring.
*   ❌ **Contract Drift:** OpenAPI schema is generated on-the-fly. No "Snapshot" verification exists to prevent accidental breaking changes between releases.

---

## 6. Access Control Matrix (Role Mapping)

| Role | Listings | Orders | Escrow Transactions | Admin |
| :--- | :--- | :--- | :--- | :--- |
| **Buyer** | View/Like | View/Cancel (Own) | - (Initiate Payment) | ❌ |
| **Seller** | Manage (Own) | Update Tracking | View (Linked to Own) | ❌ |
| **Agent** | Manage (All) | - | - | ❌ |
| **Staff** | Toggle Ver. | Resolve Disputes | Manage Payouts | ✅ |

🚨 **Flag:** 
*   ❌ **Privilege Escalation:** `IsAgent` is currently an alias to `IsSeller` (`core.permissions.py:46`), potentially granting agents permissions meant for sellers.
*   ❌ **Object-level Gaps:** Manual object-level checks scattered across view actions rather than localized in DRF's `get_object`.

---

## 7. Observability & Monitoring

*   **Sentry:** Error tracking is solid.
*   **Traceability:** Correlation IDs used across HTTP and Celery for request flow analysis.

🚨 **Flag:** 
*   ❌ **Metrics Blindness:** No application metrics (Prometheus/Grafana) for latency, order throughput, or payout success rates.
*   ❌ **Blind Spots:** No alerting configured for "Stuck Payouts" beyond logs. High risk of missing failed money movements.
*   ❌ **No SLOs:** No Service Level Objectives (e.g., 99.5% payout success) are defined or tracked.

---

## 8. Scalability & Cost Analysis

*   **Cost Drivers:** Cloudinary (Media), Selcom (Payment Fees), Postgres storage.
*   **Growth:** Multi-table inheritance (MTI) will cause JOIN explosions.

🚨 **Flag:** 
*   ❌ **Unbounded Memory:** Redis memory usage is not bounded by an eviction policy in `settings.py`. Risk of OOM in shared environments.
*   ❌ **Financial Leaks:** High transaction frequency will increase Cloudinary storage costs if old order evidence is never purged.

---

## 9. Developer Experience (Maintainability)

*   **Consitency:** Service layer is well-followed.
*   **Onboarding:** Modular apps make the code readable.

🚨 **Flag:** 
*   ❌ **Hidden Logic:** `SellerService.sync_verification_derivatives` runs synchronously on signals, making `User` saves slow and opaque.
*   ❌ **Migration Safety:** No "Zero-Downtime Migration" strategy defined (e.g., pre-deploying migrations with default values).

---

## 10. Financial System Audit (TOP PRIORITY)
**Trace:** `Cart` → `Order (PENDING)` → `Transaction (CREATED)` → `Payment (PAID)` → `Escrow (HOLD)` → `Delivery` → `Payout (RELEASED)`

### Verification
*   **Atomicity:** Checkout is wrapped in `transaction.atomic`.
*   **Idempotency:** Webhooks use `GatewayEvent` table + Redis `escrow_distributed_lock`. 
*   **State Transitions:** `escrow_engine.state_machine` strictly validates all status moves.

---

## 11. CRITICAL ISSUES (MUST FIX)
1.  **Financial Deletion Resilience:** Change `models.CASCADE` to `models.PROTECT` on all `Order` and `Transaction` user relations.
2.  **Webhook Hardening:** Implement a maximum age check (e.g., 5 mins) for webhook `Timestamp` headers to prevent delayed replays.
3.  **Secrets Lockdown:** Remove all fallback/default keys from `settings.py`. Use `raise ValueError` if missing in production.
4.  **Payout Authorization:** Implement dual-authorization for manual payout processing via Admin.
5.  **Redis Scaling:** Decouple standard Cache from the critical Celery/Lock broker in production.

---

## 12. Strategic Improvements
*   **Short Term:** Migrate `MarketplaceItem` from Multi-table Inheritance to a single-table or decoupled model.
*   **Medium Term:** Implement Prometheus metrics + Grafana dashboard for financial alerts.
*   **Long Term:** Extract `escrow_engine` into a standalone service with its own DB.
