# SmartDalali Bug Fixes Report

## Summary
Reviewed all 18 view files, 15 API routes, and key components (product-card, category-bar). Found and fixed **18 distinct issues** across the codebase.

---

## Issues Found & Fixed

### 1. Listings API Response Shape Mismatch (HIGH)
**Affected Files:** `home-page.tsx`, `search-page.tsx`, `category-page.tsx`, `seller-listings.tsx`, `product-page.tsx` (related products)

**Problem:** API returns `{ success, data: { listings: [...], pagination } }` but views were extracting from `data.results` or `data.listings` inconsistently.

**Fix:** Created `normalizeListing()` helper in `lib/helpers.ts` and updated all views to:
- Extract from `res.data?.listings` instead of `res.data?.results`
- Normalize each listing to convert `image` (string) to `images` (array), fill missing `seller.username` from `seller.name`, and populate `_count.reviews`

### 2. Listing Image Format Mismatch (HIGH)
**Problem:** The listings list API returns each listing with `image` (single string URL), but the `Listing` TypeScript type and `ProductCard` component expect `images` (array of `ListingImage` objects).

**Fix:** Added `normalizeListing()` helper that converts `image: string | null` into `images: ListingImage[]` so ProductCard's `listing.images?.find(...)` and `listing.images?.[0]` work correctly.

### 3. Category Count Field Name Mismatch (MEDIUM)
**Affected File:** `category-bar.tsx`

**Problem:** Categories API returns `listingCount: number` but CategoryBar accessed `cat._count?.listings`.

**Fix:** Changed to `cat.listingCount`.

### 4. Cart Item Image Field Mismatch (HIGH)
**Affected Files:** `cart-page.tsx`, `checkout-page.tsx`

**Problem:** Cart API returns each item's listing with `image: string | null`, but views accessed `item.listing.images?.[0]?.url`.

**Fix:** Changed to `item.listing.image` in both files.

### 5. Cart Item Listing ID Access (HIGH)
**Affected File:** `cart-page.tsx`

**Problem:** Cart page navigated with `item.listingId` but cart API doesn't include `listingId` at the item level (it's nested under `item.listing.id`).

**Fix:** Changed `item.listingId` → `item.listing.id` (2 occurrences).

### 6. Add-to-Cart Response Not Full Cart (CRITICAL)
**Affected Files:** `product-page.tsx` (2 handlers), `product-card.tsx`

**Problem:** Add-to-cart API returns `{ success, data: { id, quantity, listingId, ... } }` (single cart item). Views called `setCart(res.data || res)` which set the entire cart store to a single item object, breaking all cart displays.

**Fix:** After successful add-to-cart, re-fetch the full cart with `api.getCart(user.id)` and pass that to `setCart()`.

### 7. Update Cart Quantity / Remove Response (CRITICAL)
**Affected File:** `cart-page.tsx`

**Problem:** `updateCartQuantity` and `removeFromCart` APIs return single item/message, not the full cart. Same bug as #6.

**Fix:** Both handlers now re-fetch the full cart after successful operations.

### 8. Orders API Response Shape (HIGH)
**Affected Files:** `orders-page.tsx`, `seller-orders.tsx`

**Problem:** Orders API returns `{ success, data: { orders: [...], pagination } }` but views extracted from `data.results`.

**Fix:** Changed to `res.data?.orders` in orders-page, `data.orders` in seller-orders.

### 9. Reviews API Response Shape (HIGH)
**Affected File:** `product-page.tsx`

**Problem:** Reviews API returns `{ success, data: { reviews: [...], averageRating, ... } }` but view extracted from `data.results`.

**Fix:** Changed to `res.data?.reviews` (2 occurrences: initial load + refresh after submit).

### 10. Login/Register User Extraction (CRITICAL)
**Affected Files:** `login-page.tsx`, `register-page.tsx`

**Problem:** Auth APIs return `{ success, data: { id, email, username, ... } }` — user data is directly in `data`. Views tried to access `result.data?.user` which was `undefined`, causing login/register to fail silently.

**Fix:** Changed to `(result.data || result)` which correctly extracts the user object.

### 11. Seller Dashboard Stats Structure (HIGH)
**Affected File:** `seller-dashboard.tsx`

**Problem:** Dashboard API returns `{ stats: { totalOrders, totalRevenue, ... }, recentOrders, monthlyRevenue }`. View accessed `dashboard.totalOrders` directly instead of `dashboard.stats.totalOrders`.

**Fix:** Extracted `stats` from `raw.stats`, `recentOrders` from `raw.recentOrders`, and converted `monthlyRevenue` from `Record<string, number>` to `Array<{ month, revenue }>`.

### 12. Seller Payouts Response Shape (HIGH)
**Affected File:** `seller-payouts.tsx`

**Problem:** Payouts API returns `{ payouts: [...], summary, pagination }` but view extracted from `data.results`.

**Fix:** Changed to `data.payouts`.

### 13. Payment Initiate Response Structure (HIGH)
**Affected File:** `payment-confirmation.tsx`

**Problem:** Initiate payment API returns `{ transaction: {...}, paymentUrl, message }`. View accessed `txnData.id` and `txnData.providerRef` directly, but those are on `txnData.transaction.*`.

**Fix:** Added `const txnData = txnWrapper.transaction || txnWrapper` to unwrap the nested transaction.

### 14. Review Reviewer Name Field (MEDIUM)
**Affected File:** `product-page.tsx`

**Problem:** Reviews API includes `reviewer: { id, name, avatar }` (no `username`). View accessed `review.reviewer.username` which was `undefined`.

**Fix:** Changed to `review.reviewer.username || review.reviewer.name` with fallback.

### 15. Seller Listings Response Shape (MEDIUM)
**Affected File:** `seller-listings.tsx`

**Problem:** Seller listings API returns `{ listings: [...], pagination }` but view only checked `data.results`.

**Fix:** Changed to `data.results ?? data.listings ?? []`.

---

## Files Modified
1. `src/lib/helpers.ts` — Added `normalizeListing()` helper
2. `src/views/home-page.tsx` — Listings extraction + normalization
3. `src/views/product-page.tsx` — Reviews extraction, cart re-fetch, related products, reviewer name
4. `src/views/cart-page.tsx` — Image field, listingId, cart re-fetch on update/remove
5. `src/views/checkout-page.tsx` — Image field
6. `src/views/search-page.tsx` — Listings extraction + normalization
7. `src/views/category-page.tsx` — Listings extraction + normalization
8. `src/views/orders-page.tsx` — Orders extraction
9. `src/views/seller-orders.tsx` — Orders extraction
10. `src/views/login-page.tsx` — User extraction
11. `src/views/register-page.tsx` — User extraction
12. `src/views/seller-dashboard.tsx` — Stats + monthlyRevenue conversion
13. `src/views/seller-payouts.tsx` — Payouts extraction
14. `src/views/payment-confirmation.tsx` — Transaction unwrapping
15. `src/views/seller-listings.tsx` — Listings extraction
16. `src/components/smartdalali/product-card.tsx` — Cart re-fetch after add
17. `src/components/smartdalali/category-bar.tsx` — listingCount field
