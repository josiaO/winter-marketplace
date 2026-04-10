# SmartDalali Marketplace Engine Architecture

## Overview

SmartDalali has been transformed from a property-focused platform into a **universal marketplace engine** similar to Amazon/AliExpress, while maintaining full backward compatibility with existing property listings.

## Architecture Principles

1. **Universal Listing Model**: All sellable/rentable items use the same `Listing` model
2. **Dynamic Catalog System**: Categories define allowed fields/specs via JSON
3. **Backward Compatibility**: Property listings remain functional as a category
4. **Incremental Migration**: No breaking changes to existing APIs
5. **Shared Abstractions**: Core models reused across all listing types

---

## Core Systems

### 1. Universal Listing Engine

**Location**: `backend/core/models/listing.py` → `backend/listings/models.py`

**BaseListing Model** (Abstract):
- Universal model for all listing types (properties, products, services)
- Category-based dynamic attributes via `specs` JSONField
- Inventory management (stock tracking, reservations)
- Trust & safety flags (verification, price anomaly detection)

**Key Features**:
- `stock_quantity`: Available inventory
- `track_inventory`: Enable/disable stock tracking
- `is_verified`: Admin verification status
- `is_flagged`: Suspicious activity flag
- `price_anomaly_score`: Automated price anomaly detection

**Methods**:
- `is_in_stock(quantity)`: Check stock availability
- `reserve_stock(quantity)`: Reserve inventory
- `release_stock(quantity)`: Release reserved stock
- `is_low_stock()`: Check if below threshold

**Listing Model** (Concrete):
- Inherits from `BaseListing`
- Used by all listing types (Property, MarketplaceItem)

---

### 2. Dynamic Catalog System

**Location**: `backend/catalog/models.py`

**Category Model**:
- Hierarchical categories (parent/child relationships)
- Vertical classification (property, vehicle, electronics, etc.)
- Service vs. physical product flags

**CategoryField Model**:
- Defines dynamic specs for each category
- Field types: text, number, select, boolean, date
- Required/optional validation
- Unit specifications (GB, square meters, etc.)

**Usage**:
```python
# Property category might have: bedrooms, bathrooms, area
# Electronics category might have: brand, model, storage
# All stored in listing.specs JSONField
```

---

### 3. Seller/Store System

**Location**: `backend/marketplace/models.py`

**SellerProfile Model**:
- Extends user account with seller-specific information
- Business information (name, type, tax ID)
- Verification status and documents
- Ratings summary (denormalized for performance)
- Suspension/activation status

**Store Model**:
- Storefronts for sellers (can have multiple stores)
- Store branding (logo, banner, description)
- Social media links
- Statistics (listings, sales, followers)

**StoreFollow Model**:
- Users following stores
- Enables store notifications and recommendations

**Key Features**:
- Seller verification workflow
- Store statistics auto-calculation
- Follow/unfollow functionality

---

### 4. Inventory System

**Location**: `backend/core/models/listing.py` + `backend/commerce/models.py`

**Stock Management**:
- `stock_quantity`: Available units
- `track_inventory`: Enable/disable tracking
- `low_stock_threshold`: Alert threshold
- `allow_backorders`: Allow orders when out of stock

**StockReservation Model**:
- Reserves inventory during checkout process
- Prevents overselling
- Auto-expires after 30 minutes (configurable)
- Status: reserved → confirmed → released/expired

**Service**: `InventoryService` in `marketplace/services.py`
- `reserve_stock()`: Create reservation
- `confirm_reservation()`: Convert to order
- `release_reservation()`: Release back to inventory
- `cleanup_expired_reservations()`: Maintenance task

---

### 5. Transactions & Escrow

**Location**: `backend/commerce/models.py`

**Order Model** (Consolidated):
- **Financial Breakdown**:
  - `subtotal`: Sum of order items
  - `shipping_cost`: Delivery cost
  - `platform_fee`: Commission (default 5%)
  - `total_amount`: Total (subtotal + shipping + fee)
- **Status Flow**: pending → confirmed → processing → shipped → delivered → completed
- **Shipping**: Address, method, tracking number
- **Notes**: Buyer and seller notes

**OrderItem Model**:
- Links order to listing
- Quantity and price snapshot
- Protected (cannot delete listing if in order)

**EscrowTransaction Model**:
- Payment protection system
- Status: held → released/refunded/disputed
- Payment method tracking
- Dispute handling

**Payout Model**:
- Seller payout after escrow release
- Status: pending → processing → completed/failed
- Payout method (M-Pesa, bank transfer, etc.)

**Transaction Model** (in `transactions/models.py`):
- Payment records for orders
- Multiple payment methods
- Gateway transaction tracking

**Dispute Model** (in `transactions/models.py`):
- Order dispute resolution
- Admin mediation
- Resolution tracking

---

### 6. Delivery/Logistics

**Location**: `backend/commerce/models.py`

**Delivery Model**:
- Shipping tracking for orders
- Methods: shipping, pickup, digital, local_delivery
- Address management (recipient, full address)
- Tracking: carrier, tracking number, tracking URL
- Status: pending → preparing → in_transit → out_for_delivery → delivered
- Timestamps: shipped_at, estimated_delivery, delivered_at

**Features**:
- Multiple delivery methods
- Carrier integration ready
- Delivery notes and signature requirements

---

### 7. Platform Fees & Commissions

**Location**: `backend/commerce/models.py` + `backend/marketplace/services.py`

**Fee Calculation**:
- Default: 5% of subtotal (configurable)
- Calculated in `OrderService.calculate_platform_fee()`
- Can be made dynamic based on:
  - Seller tier
  - Category
  - Listing type

**Order Financial Breakdown**:
```python
subtotal = sum(order_items)
platform_fee = calculate_platform_fee(subtotal)
shipping_cost = calculate_shipping(order)
total_amount = subtotal + platform_fee + shipping_cost
seller_payout = subtotal - platform_fee
```

---

### 8. Trust & Anti-Scam

**Location**: `backend/trust/models.py` (verification, reviews, reports, trust scores, moderation)

**UserVerification Model**:
- Identity verification status
- Document type tracking
- Verification date

**ListingVerification Model**:
- Deep verification for high-value listings
- Admin verification workflow
- Verification notes

**ReputationScore Model**:
- Aggregated trust score (0-100)
- Based on: verification, reviews, transactions, violations

**Review Model**:
- User reviews for listings and sellers
- Rating (1-5 stars)
- Verified purchase flag
- Moderation flags

**Report Model**:
- User reports for listings, users, reviews
- Report types: spam, fraud, inappropriate, misleading, harassment
- Status: pending → under_review → resolved/dismissed

**PriceAnomaly Model**:
- Automated price anomaly detection
- Anomaly types: too_low, too_high, price_drop, price_spike, category_mismatch
- Score (0-1): higher = more suspicious
- Expected vs. actual price comparison
- Admin review workflow

**ModerationAction Model**:
- Admin actions: warn, suspend, ban, verify, delete
- Target types: listing, user, review
- Duration tracking for temporary actions

**Price Anomaly Detection Service**:
- `PriceAnomalyService.detect_price_anomaly()`
- Compares listing price to category average
- Flags significant deviations (>30%)
- Updates listing `price_anomaly_score`

---

## Seller Onboarding (Progressive Verification)

**Principle:** Trust is earned on both sides. Ask for data only when the seller needs the next capability — not everything at signup.

### Stages (product flow)

| Stage | When | Collect | Unlock |
|-------|------|---------|--------|
| **1 — Sign up** | Day 0 (~2 min) | Name, email/phone, password, intent (buy/sell/both) | Account + seller welcome; browse dashboard; **readiness indicator** (e.g. “store 20% ready”) |
| **2 — Store setup** | Day 0 (~5 min) | Store name, primary category, city/region | Store page **pending verification**; **listings as drafts** (`is_published=False`) so they can invest before ID |
| **3 — Identity** | First **publish** attempt (not a cold email) | Legal name, ID type/number, ID front, **selfie with ID**; optional “do later” with dashboard reminders | After admin review (~24h, SMS + email): identity cleared; **first publish** allowed |
| **4 — Payouts** | Right after identity approved | Mobile money (M-Pesa / Tigo Pesa / Airtel Money); **optional TZS 1 confirmation** | Receive payouts (`Payout` / escrow release) |
| **5 — Business (optional)** | Milestone (e.g. TZS 500k sales or 20 orders) | Business cert (optional), TIN (optional), bank for large payouts | Higher limits, **Verified Business** badge, bulk tools |

### Rules (UX and policy)

- **Never ask before they need it** — e.g. no TIN at signup.
- **Always explain why** — e.g. ID is for buyer trust, not a blank upload.
- **Always show what unlocks** — go live, get paid, remove limits.
- **Drafts before verification** — intentional commitment device; `Listing.is_published` stays `False` until identity (and any other gates) pass.

### Mapping to current backend

| Roadmap concept | Model / field / behavior |
|-----------------|---------------------------|
| Draft listings | `Listing.is_published` (default `False`); public APIs filter `is_published=True` |
| Store + seller basics | `SellerProfile`, `Store` — keep `tax_id` and heavy fields **empty until Stage 5** in UX; fields already allow blank where appropriate |
| Identity (ID + review) | `trust.UserVerification` — `national_id_*`, `id_status`; extend with **selfie** file field if not present |
| TIN / license deferred | Same model has `tin_*`, `business_license_*` — **only expose in UI at Stage 5** or when submitting business upgrade |
| Seller badge | `SellerProfile.is_verified`, `verified_at`, `verification_documents` |
| Payouts / mobile money | `commerce.Payout`, payment method fields — collect at Stage 4, not signup |
| Milestone for Stage 5 | `SellerProfile.total_sales` (and/or order aggregates) vs configurable thresholds |

### Implementation notes

- **Gate publish:** On “publish first product”, if `UserVerification` identity is not verified, return a structured response that drives the **Almost ready to go live** modal (do not block draft CRUD).
- **Store readiness %:** Derive from checklist (account → store → draft listing → ID → payout method → optional business) for the dashboard progress bar.
- **Stage 5:** Store flags such as `is_business_verified` / tier limits (product caps, payout caps) if not already modeled; tie to the same `UserVerification` TIN/license paths admin already uses.

---

## App Structure

```
backend/
├── core/
│   └── models/
│       ├── base.py          # BaseModel
│       └── listing.py        # BaseListing (abstract)
├── listings/
│   └── models.py            # Listing (concrete)
├── catalog/
│   └── models.py            # Category, CategoryField
├── marketplace/
│   ├── models.py            # SellerProfile, Store, StoreFollow
│   ├── serializers.py       # Seller/Store serializers
│   └── services.py          # Marketplace services
├── commerce/
│   ├── models.py            # Order, OrderItem, Cart, Escrow, Payout, Delivery, StockReservation
│   └── serializers.py       # Commerce serializers
├── transactions/
│   └── models.py            # Transaction, Dispute (uses commerce.Order)
├── trust/
│   └── models.py            # Verification, PriceAnomaly, Review, Report, TrustScore, ModerationAction, …
└── properties/
    └── models.py            # Property (extends Listing, backward compatible)
```

---

## Backward Compatibility

### Property Listings

**Current State**:
- `Property` model extends `Listing`
- All existing property fields preserved
- Property-specific fields: `type`, `area`, `bedrooms`, `bathrooms`, etc.
- Legacy fields: `adress` (typo preserved for compatibility)

**Migration Path**:
1. Properties continue to work as-is
2. Property fields can be migrated to `specs` JSONField gradually
3. No breaking changes to existing APIs
4. Frontend continues to work with property endpoints

**Property as Category**:
- Properties are now a category in the catalog system
- Can use dynamic specs for property-specific attributes
- Maintains all existing functionality

---

## Key Services

### InventoryService
- Stock reservation management
- Expiration handling
- Cleanup tasks

### OrderService
- Order creation from cart
- Platform fee calculation
- Order cancellation with stock release

### PriceAnomalyService
- Automated price anomaly detection
- Category-based price comparison
- Anomaly scoring

### SellerService
- Seller profile management
- Rating updates
- Store statistics

---

## Database Migrations

**Required Migrations**:
1. `core`: Add inventory fields to BaseListing
2. `marketplace`: Create SellerProfile, Store, StoreFollow
3. `commerce`: Enhance Order, add Delivery, StockReservation
4. `trust`: Add PriceAnomaly
5. `transactions`: Update to reference commerce.Order

**Migration Strategy**:
- All new fields are nullable or have defaults
- No data loss
- Backward compatible
- Can be applied incrementally

---

## API Endpoints (To Be Implemented)

### Listings
- `GET /api/listings/` - Universal listings
- `GET /api/listings/{id}/` - Listing detail
- `POST /api/listings/` - Create listing
- `PUT /api/listings/{id}/` - Update listing

### Sellers
- `GET /api/sellers/` - List sellers
- `GET /api/sellers/{id}/` - Seller profile
- `POST /api/sellers/` - Create seller profile

### Stores
- `GET /api/stores/` - List stores
- `GET /api/stores/{slug}/` - Store detail
- `POST /api/stores/{id}/follow/` - Follow store

### Orders
- `GET /api/orders/` - List orders
- `POST /api/orders/` - Create order from cart
- `GET /api/orders/{id}/` - Order detail

### Cart
- `GET /api/cart/` - Get cart
- `POST /api/cart/items/` - Add to cart
- `DELETE /api/cart/items/{id}/` - Remove from cart

---

## Next Steps

1. **Create Migrations**: Run `python manage.py makemigrations`
2. **Apply Migrations**: Run `python manage.py migrate`
3. **Create Admin Interfaces**: Register new models in admin
4. **Create API Views**: Implement REST endpoints
5. **Add Tests**: Unit and integration tests
6. **Documentation**: API documentation
7. **Frontend Integration**: Update frontend to use new endpoints

---

## Notes

- All models use `BaseModel` (created_at, updated_at)
- All models have proper indexes for performance
- JSONFields use PostgreSQL GinIndex for efficient querying
- Services handle business logic, models handle data
- Serializers provide API representation
- Backward compatibility maintained throughout

---

## Questions or Issues?

Refer to:
- Model docstrings for field descriptions
- Service methods for business logic
- Serializers for API structure
- This document for architecture overview
