import type {
  ApiError,
  TokenResponse,
  TokenResponseWithUser,
  User,
  Listing,
  Category,
  CategoryField,
  CategoryAttribute,
  Store,
  Cart,
  CartItem,
  Order,
  OrderItem,
  WishlistItem,
  Transaction,
  Payout,
  Review,
  Report,
  Verification,
  Conversation,
  Message,
  Notification,
  Dispute,
  Plan,
  Subscription,
  PayLink,
  Feature,
  AdminStats,
  GrowthCharts,
  SellerStats,
  PlatformMetrics,
  UserStats,
  PaymentMethodOption,
  SupportRequest,
  DeviceToken,
  PaginatedResponse,
  LoginPayload,
  RegisterPayload,
  PasswordResetPayload,
  PasswordResetConfirmPayload,
  ChangePasswordPayload,
  BecomeSellerPayload,
  OtpPayload,
  OtpVerifyPayload,
  CreateListingPayload,
  UpdateListingPayload,
  CheckoutPayload,
  ShippingOptionRow,
  ConfirmPaymentReturnPayload,
  ConfirmPaymentReturnResponse,
  CreateReviewPayload,
  CreateListingOfferPayload,
  ListingOffer,
  CreateReportPayload,
  CreateDisputePayload,
  ResolveDisputePayload,
  CreatePayLinkPayload,
} from '@/types/api';
import { ApiClientError } from '@/types/api';

// =============================================================================
// Configuration
// =============================================================================

/**
 * Browser and UI code should call same-origin `/api/v1/*`.
 * Next.js proxies that to Django using NEXT_PUBLIC_API_URL / INTERNAL_API_URL.
 */
const BASE_URL = '/api/v1';

const TOKEN_ACCESS_KEY = 'sd_access_token';
const TOKEN_REFRESH_KEY = 'sd_refresh_token';

// =============================================================================
// Helpers
// =============================================================================

function buildQueryString(params?: Record<string, string | number | boolean | null | undefined>): string {
  if (!params) return '';
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.set(key, String(value));
    }
  }
  const qs = searchParams.toString();
  return qs ? `?${qs}` : '';
}

function isFormData(body: unknown): body is FormData {
  return typeof FormData !== 'undefined' && body instanceof FormData;
}

// =============================================================================
// ApiClient Class
// =============================================================================

class ApiClient {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private isRefreshing = false;
  private failedQueue: Array<{ resolve: (token: string) => void; reject: (error: unknown) => void }> = [];

  constructor() {
    if (typeof window !== 'undefined') {
      this.loadTokens();
    }
  }

  // ---------------------------------------------------------------------------
  // Token Management
  // ---------------------------------------------------------------------------

  private loadTokens(): void {
    try {
      this.accessToken = localStorage.getItem(TOKEN_ACCESS_KEY);
      this.refreshToken = localStorage.getItem(TOKEN_REFRESH_KEY);
    } catch {
      this.accessToken = null;
      this.refreshToken = null;
    }
  }

  private saveTokens(access: string, refresh: string): void {
    try {
      localStorage.setItem(TOKEN_ACCESS_KEY, access);
      localStorage.setItem(TOKEN_REFRESH_KEY, refresh);
    } catch {
      // Storage may be unavailable
    }
    this.accessToken = access;
    this.refreshToken = refresh;
  }

  private clearTokens(): void {
    try {
      localStorage.removeItem(TOKEN_ACCESS_KEY);
      localStorage.removeItem(TOKEN_REFRESH_KEY);
    } catch {
      // Storage may be unavailable
    }
    this.accessToken = null;
    this.refreshToken = null;
  }

  public getAccessToken(): string | null {
    return this.accessToken;
  }

  /** Manually set tokens (e.g., after login/register) */
  public setTokens(access: string, refresh: string): void {
    this.saveTokens(access, refresh);
  }

  public isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  private processQueue(error: unknown, token: string | null = null): void {
    this.failedQueue.forEach((promise) => {
      if (error) {
        promise.reject(error);
      } else {
        promise.resolve(token!);
      }
    });
    this.failedQueue = [];
  }

  // ---------------------------------------------------------------------------
  // Core Request
  // ---------------------------------------------------------------------------

  private async refreshAccessToken(): Promise<string> {
    if (!this.refreshToken) {
      this.clearTokens();
      throw new ApiClientError({ status: 401, message: 'No refresh token available' });
    }

    try {
      const res = await fetch(`${BASE_URL}/accounts/auth/token/refresh/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: this.refreshToken }),
      });

      if (!res.ok) {
        this.clearTokens();
        throw new ApiClientError({
          status: 401,
          message: 'Token refresh failed',
          detail: 'Your session has expired. Please log in again.',
        });
      }

      const data: TokenResponse = await res.json();
      this.saveTokens(data.access, data.refresh);
      return data.access;
    } catch (error) {
      if (error instanceof ApiClientError) throw error;
      this.clearTokens();
      throw new ApiClientError({
        status: 401,
        message: 'Token refresh failed',
        detail: String(error),
      });
    }
  }

  private async request<T>(
    path: string,
    options: RequestInit & { skipAuth?: boolean } = {},
  ): Promise<T> {
    const { skipAuth = false, ...fetchOptions } = options;

    const headers = new Headers(fetchOptions.headers);

    if (!isFormData(fetchOptions.body) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    if (this.accessToken && !skipAuth) {
      headers.set('Authorization', `Bearer ${this.accessToken}`);
    }

    let res = await fetch(`${BASE_URL}${path}`, {
      ...fetchOptions,
      headers,
    });

    // Handle 401 — attempt token refresh
    if (res.status === 401 && !skipAuth && this.refreshToken) {
      if (this.isRefreshing) {
        // Queue the request until refresh completes
        return new Promise<T>((resolve, reject) => {
          this.failedQueue.push({
            resolve: (newToken: string) => {
              headers.set('Authorization', `Bearer ${newToken}`);
              fetch(`${BASE_URL}${path}`, { ...fetchOptions, headers })
                .then((retryRes) => this.parseResponse<T>(retryRes))
                .then(resolve)
                .catch(reject);
            },
            reject,
          });
        });
      }

      this.isRefreshing = true;
      try {
        const newToken = await this.refreshAccessToken();
        this.processQueue(null, newToken);

        // Retry the original request
        headers.set('Authorization', `Bearer ${newToken}`);
        res = await fetch(`${BASE_URL}${path}`, {
          ...fetchOptions,
          headers,
        });
      } catch (refreshError) {
        this.processQueue(refreshError);
        throw refreshError;
      } finally {
        this.isRefreshing = false;
      }
    }

    return this.parseResponse<T>(res);
  }

  private async parseResponse<T>(res: Response): Promise<T> {
    if (!res.ok) {
      let errorData: ApiError;
      try {
        errorData = await res.json();
      } catch {
        errorData = {
          status: res.status,
          message: res.statusText || 'Request failed',
        };
      }
      const drfError =
        typeof (errorData as { error?: unknown }).error === 'string'
          ? (errorData as { error: string }).error
          : undefined;
      throw new ApiClientError({
        status: errorData.status || res.status,
        message: errorData.message || drfError || 'Request failed',
        detail: errorData.detail || drfError,
        errors: errorData.errors,
      });
    }

    // Handle 204 No Content
    if (res.status === 204) {
      return undefined as unknown as T;
    }

    return res.json();
  }

  // ---------------------------------------------------------------------------
  // Generic CRUD Helpers
  // ---------------------------------------------------------------------------

  private get<T>(
    path: string,
    params?: Record<string, string | number | boolean | null | undefined>,
    reqOptions?: { skipAuth?: boolean },
  ): Promise<T> {
    return this.request<T>(`${path}${buildQueryString(params)}`, {
      method: 'GET',
      skipAuth: reqOptions?.skipAuth,
    });
  }

  private post<T>(path: string, body?: unknown, options?: RequestInit & { skipAuth?: boolean }): Promise<T> {
    const headers: Record<string, string> = {};
    if (!isFormData(body)) {
      headers['Content-Type'] = 'application/json';
    }
    return this.request<T>(path, {
      method: 'POST',
      body: isFormData(body) ? body : body ? JSON.stringify(body) : undefined,
      headers,
      ...options,
    });
  }

  private put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  private patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  private delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' });
  }

  // ===========================================================================
  // AUTH ENDPOINTS
  // ===========================================================================

  auth = {
    /**
     * POST /accounts/auth/token/
     * Backend accepts either {username,password} or {email,password}.
     */
    login: (payload: LoginPayload): Promise<TokenResponseWithUser> =>
      this.post('/accounts/auth/token/', payload, { skipAuth: true }),

    /**
     * POST /accounts/auth/register/
     * Backend returns {success,message,user_id,email,phone,username} (no tokens).
     */
    register: (payload: RegisterPayload): Promise<{
      success: boolean;
      message: string;
      user_id: number;
      email: string;
      phone?: string | null;
      username: string;
    }> => this.post('/accounts/auth/register/', payload, { skipAuth: true }),

    /** POST /accounts/auth/token/refresh/ */
    refreshToken: (): Promise<TokenResponse> =>
      this.post('/accounts/auth/token/refresh/', { refresh: this.refreshToken }, { skipAuth: true }),

    /** POST /accounts/auth/logout/ */
    logout: (): Promise<void> => {
      const result = this.post('/accounts/auth/logout/', { refresh: this.refreshToken });
      this.clearTokens();
      return result as unknown as Promise<void>;
    },

    /** POST /accounts/auth/password-reset/ */
    passwordReset: (payload: PasswordResetPayload): Promise<{ message: string }> =>
      this.post('/accounts/auth/password-reset/', payload, { skipAuth: true }),

    /** POST /accounts/auth/password-reset/confirm/ */
    passwordResetConfirm: (payload: PasswordResetConfirmPayload): Promise<{ message: string }> =>
      this.post('/accounts/auth/password-reset/confirm/', payload, { skipAuth: true }),

    /** GET|PATCH /accounts/me/ */
    me: (): Promise<User> => this.get('/accounts/me/'),

    /** POST /accounts/profile/change-password/ */
    changePassword: (payload: ChangePasswordPayload): Promise<{ message: string }> =>
      this.post('/accounts/profile/change-password/', payload),

    /** DELETE /accounts/profile/delete/ (requires OTP code) */
    deleteAccount: (payload: { code: string; refresh?: string }): Promise<{ message: string }> =>
      this.request('/accounts/profile/delete/', {
        method: 'DELETE',
        body: JSON.stringify(payload),
        headers: { 'Content-Type': 'application/json' },
      }),

    /** POST /accounts/profile/become-seller/ (returns fresh tokens + user summary) */
    becomeSeller: (): Promise<{
      message: string;
      seller_profile_id: number | null;
      already_seller: boolean;
      access: string;
      refresh: string;
      user: unknown;
    }> => this.post('/accounts/profile/become-seller/', undefined),

    /** POST /accounts/otp/request/ */
    requestOtp: (
      payload: OtpPayload & { purpose?: string; user_id?: number; channel?: string }
    ): Promise<{ message: string; expires_in_minutes?: number }> =>
      this.post('/accounts/otp/request/', payload, { skipAuth: true }),

    /** POST /accounts/otp/verify/ */
    verifyOtp: (
      payload: OtpVerifyPayload & { purpose?: string; email?: string; user_id?: number }
    ): Promise<{ message: string; verified?: boolean; reset_token?: string }> =>
      this.post('/accounts/otp/verify/', payload, { skipAuth: true }),
  };

  // ===========================================================================
  // LISTINGS ENDPOINTS
  // ===========================================================================

  listings = {
    /** GET /listings/ */
    list: (params?: Record<string, string | number | boolean | null | undefined>): Promise<PaginatedResponse<Listing>> =>
      this.get('/listings/', params),

    /** GET /listings/:id/ */
    detail: (id: number | string): Promise<Listing> => this.get(`/listings/${id}/`),

    /** GET /listings/seller/ (current user's listings) */
    sellerListings: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<{ results: Listing[]; count: number } | PaginatedResponse<Listing>> =>
      this.get('/listings/seller/', params),

    /** POST /listings/ (multipart supported: media[]) */
    create: (payload: CreateListingPayload): Promise<Listing> => {
      const anyPayload = payload as unknown as Record<string, unknown>;
      const media = (anyPayload.media as File[] | undefined) || (anyPayload.images as File[] | undefined);
      if (media && media.length > 0) {
        const fd = new FormData();
        for (const [key, value] of Object.entries(anyPayload)) {
          if (key === 'media' || key === 'images') continue;
          if (value !== undefined && value !== null) {
            fd.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
          }
        }
        media.forEach((f) => fd.append('media', f));
        return this.post('/listings/', fd);
      }
      return this.post('/listings/', payload);
    },

    /** PATCH /listings/:id/ (multipart supported: media[]) */
    update: (id: number | string, payload: UpdateListingPayload): Promise<Listing> => {
      const anyPayload = payload as unknown as Record<string, unknown>;
      const media = (anyPayload.media as File[] | undefined) || (anyPayload.images as File[] | undefined);
      if (media && media.length > 0) {
        const fd = new FormData();
        for (const [key, value] of Object.entries(anyPayload)) {
          if (key === 'media' || key === 'images' || key === 'id') continue;
          if (value !== undefined && value !== null) {
            fd.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
          }
        }
        media.forEach((f) => fd.append('media', f));
        return this.request(`/listings/${id}/`, { method: 'PATCH', body: fd });
      }
      const { id: _id, media: _m, images: _i, ...data } = anyPayload;
      void _id; void _m; void _i;
      return this.patch(`/listings/${id}/`, data);
    },

    /** DELETE /listings/:id/ */
    delete: (id: number | string): Promise<void> => this.delete(`/listings/${id}/`),

    /** POST /listings/:id/like/ (toggles like/unlike) */
    toggleLike: (id: number | string): Promise<{ status: 'liked' | 'unliked' }> =>
      this.post(`/listings/${id}/like/`),

    /** GET /listings/search/ */
    search: (params?: Record<string, string | number | boolean | null | undefined>): Promise<PaginatedResponse<Listing>> =>
      this.get('/listings/search/', params),

    /** POST /listings/:id/toggle_verified/ (admin) */
    toggleVerified: (id: number | string): Promise<{ is_verified: boolean }> =>
      this.post(`/listings/${id}/toggle_verified/`),

    /** POST /listings/:id/toggle_featured/ (admin) */
    toggleFeatured: (id: number | string): Promise<{ is_featured: boolean }> =>
      this.post(`/listings/${id}/toggle_featured/`),
  };

  // ===========================================================================
  // CATALOG ENDPOINTS
  // ===========================================================================

  catalog = {
    /** GET /catalog/categories/ */
    categories: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<Category> | Category[]> =>
      this.get('/catalog/categories/', params),

    /** GET /catalog/categories/:slug/ or /catalog/categories/:id/ */
    categoryDetail: (slugOrId: string | number): Promise<Category> =>
      this.get(`/catalog/categories/${slugOrId}/`),

    /** GET /catalog/categories/:id/fields/ */
    categoryFields: (categoryId: number | string): Promise<CategoryField[]> =>
      this.get(`/catalog/categories/${categoryId}/fields/`),

    /** GET /catalog/categories/:id/attributes/ */
    categoryAttributes: (categoryId: number | string): Promise<CategoryAttribute[]> =>
      this.get(`/catalog/categories/${categoryId}/attributes/`),

    /** GET /catalog/categories/:id/subcategories/ */
    subcategories: (categoryId: number | string): Promise<PaginatedResponse<Category>> =>
      this.get(`/catalog/categories/${categoryId}/subcategories/`),

    /** POST /catalog/categories/suggest-from-title/ (authenticated) */
    suggestFromTitle: (payload: { title: string }): Promise<{
      category_id: number | null;
      parent_name: string | null;
      category_name: string | null;
      confidence: number;
    }> => this.post('/catalog/categories/suggest-from-title/', payload),

    // -----------------------------------------------------------------------
    // Admin catalog management (requires admin/staff JWT)
    // -----------------------------------------------------------------------

    /** POST /catalog/categories/ (admin) */
    createCategory: (payload: Partial<Category> & { name: string; slug: string }): Promise<Category> =>
      this.post('/catalog/categories/', payload),

    /** PATCH /catalog/categories/:slug_or_id/ (admin) */
    updateCategory: (
      slugOrId: string | number,
      payload: Partial<Category> & Record<string, unknown>,
    ): Promise<Category> => this.patch(`/catalog/categories/${slugOrId}/`, payload),

    /** DELETE /catalog/categories/:slug_or_id/ (admin) */
    deleteCategory: (slugOrId: string | number): Promise<void> =>
      this.request(`/catalog/categories/${slugOrId}/`, { method: 'DELETE' }),

    /** GET /catalog/category-fields/?category=:id (admin/read) */
    categoryFieldsByCategory: (categoryId: number | string): Promise<CategoryField[]> =>
      this.get('/catalog/category-fields/', { category: categoryId }),

    /** POST /catalog/category-fields/ (admin) */
    createCategoryField: (payload: Partial<CategoryField> & { category: number }): Promise<CategoryField> =>
      this.post('/catalog/category-fields/', payload),

    /** PATCH /catalog/category-fields/:id/ (admin) */
    updateCategoryField: (id: number | string, payload: Partial<CategoryField> & Record<string, unknown>): Promise<CategoryField> =>
      this.patch(`/catalog/category-fields/${id}/`, payload),

    /** DELETE /catalog/category-fields/:id/ (admin) */
    deleteCategoryField: (id: number | string): Promise<void> =>
      this.request(`/catalog/category-fields/${id}/`, { method: 'DELETE' }),
  };

  // ===========================================================================
  // COMMERCE ENDPOINTS
  // ===========================================================================

  commerce = {
    /** GET /commerce/cart/ */
    cart: (): Promise<Cart> => this.get('/commerce/cart/'),

    /** GET /commerce/cart/shipping_options/ — server fees for checkout */
    shippingOptions: (): Promise<{ options: ShippingOptionRow[] }> =>
      this.get('/commerce/cart/shipping_options/'),

    /** POST /commerce/cart/add_item/ */
    cartAddItem: (payload: { listing_id: number | string; quantity?: number }): Promise<Cart> =>
      this.post('/commerce/cart/add_item/', payload),

    /** POST /commerce/cart/remove_item/ */
    cartRemoveItem: (payload: { item_id: number | string }): Promise<Cart> =>
      this.post('/commerce/cart/remove_item/', payload),

    /**
     * Set cart line to an absolute quantity (backend has no PATCH cart-item route).
     * remove_item + add_item preserves server-side price_at_time rules.
     */
    cartSetItemQuantity: async (
      itemId: number | string,
      listingId: number | string,
      newQuantity: number,
    ): Promise<Cart> => {
      await this.post('/commerce/cart/remove_item/', { item_id: itemId });
      if (newQuantity < 1) {
        return this.cart();
      }
      return this.post('/commerce/cart/add_item/', {
        listing_id: listingId,
        quantity: newQuantity,
      });
    },

    /** POST /commerce/cart/checkout/ */
    checkout: (
      payload: CheckoutPayload & {
        redirect_url?: string;
        cancel_url?: string;
      },
    ): Promise<Order | Order[]> => this.post('/commerce/cart/checkout/', payload),

    /**
     * POST /commerce/orders/confirm-payment-return/
     * Server verifies with payment provider; never trust URL "success" alone.
     */
    confirmPaymentReturn: (
      payload: ConfirmPaymentReturnPayload | { ref: string },
    ): Promise<ConfirmPaymentReturnResponse> => {
      const body =
        'ref' in payload
          ? { transaction_reference: payload.ref }
          : { transaction_reference: payload.transaction_reference };
      return this.post('/commerce/orders/confirm-payment-return/', body);
    },

    /** Buyer cancels via PATCH { status: 'cancelled' } (OrderLifecycleManager). */
    cancelOrderAsBuyer: (
      id: number | string,
    ): Promise<{ success: boolean; order: Order }> =>
      this.patch(`/commerce/orders/${id}/`, { status: 'cancelled' }),

    /** GET /commerce/orders/ */
    orders: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<Order>> =>
      this.get('/commerce/orders/', params),

    /** GET /commerce/orders/:id/ */
    orderDetail: (id: number | string): Promise<Order> =>
      this.get(`/commerce/orders/${id}/`),

    /** POST /commerce/orders/:id/initiate-payment/ */
    initiatePayment: (
      id: number | string,
      payload?: { payment_method?: string; payment_channel?: string; buyer_phone?: string; redirect_url?: string; cancel_url?: string }
    ): Promise<{ success: boolean; payment_url?: string; gateway_reference?: string; transaction_reference?: string; error?: string }> =>
      this.post(`/commerce/orders/${id}/initiate-payment/`, payload),

    /** POST /commerce/orders/:id/confirm_receipt/ */
    confirmReceipt: (id: number | string): Promise<{ success: boolean; order: Order }> =>
      this.post(`/commerce/orders/${id}/confirm_receipt/`),

    /**
     * POST /commerce/orders/:id/ship_order/ (seller).
     * Use JSON for tracking only; FormData when uploading shipment evidence.
     */
    shipOrder: (
      id: number | string,
      payload: {
        tracking_number: string;
        carrier?: string;
        shipping_method?: string;
        shipment_video?: File;
        shipment_images?: File[];
      },
    ): Promise<{ success: boolean; order: Order }> => {
      const hasFiles =
        Boolean(payload.shipment_video) ||
        (payload.shipment_images && payload.shipment_images.length > 0);
      if (hasFiles) {
        const fd = new FormData();
        fd.append('tracking_number', payload.tracking_number);
        if (payload.carrier) fd.append('carrier', payload.carrier);
        if (payload.shipping_method)
          fd.append('shipping_method', payload.shipping_method);
        if (payload.shipment_video)
          fd.append('shipment_video', payload.shipment_video);
        payload.shipment_images?.forEach((f) =>
          fd.append('shipment_images', f),
        );
        return this.post(`/commerce/orders/${id}/ship_order/`, fd);
      }
      return this.post(`/commerce/orders/${id}/ship_order/`, {
        tracking_number: payload.tracking_number,
        ...(payload.carrier ? { carrier: payload.carrier } : {}),
        ...(payload.shipping_method
          ? { shipping_method: payload.shipping_method }
          : {}),
      });
    },
    
    /** POST /commerce/orders/:id/mark_arrived/ */
    markArrived: (id: number | string): Promise<{ success: boolean; order: Order }> =>
      this.post(`/commerce/orders/${id}/mark_arrived/`),

    /** POST /commerce/orders/:id/open_dispute/ */
    openDispute: (id: number | string, payload: CreateDisputePayload & { dispute_reason: string }): Promise<{ success: boolean; order: Order }> => {
      const fd = new FormData();
      for (const [key, value] of Object.entries(payload)) {
        if (key === 'evidence_video' && value instanceof File) {
          fd.append('evidence_video', value);
        } else if (key === 'evidence_images' && Array.isArray(value)) {
          value.forEach((f: File) => fd.append('evidence_images', f));
        } else if (value !== undefined && value !== null) {
          fd.append(key, String(value));
        }
      }
      return this.post(`/commerce/orders/${id}/open_dispute/`, fd);
    },

    /** POST /commerce/orders/:id/review/ (multipart when images provided) */
    reviewOrder: (
      id: number | string,
      payload: { rating: number; comment?: string },
      images?: File[],
    ): Promise<Review> => {
      if (images && images.length > 0) {
        const fd = new FormData();
        fd.append('rating', String(payload.rating));
        fd.append('comment', payload.comment ?? '');
        images.forEach((f) => fd.append('images', f));
        return this.post(`/commerce/orders/${id}/review/`, fd);
      }
      return this.post(`/commerce/orders/${id}/review/`, payload);
    },

    /** GET /commerce/offers/ */
    offers: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<ListingOffer>> => this.get('/commerce/offers/', params),

    /** GET /commerce/offers/active-count/ */
    offersActiveCount: (): Promise<{ active_count: number; max: number }> =>
      this.get('/commerce/offers/active-count/'),

    /** POST /commerce/offers/ */
    offersCreate: (payload: CreateListingOfferPayload): Promise<ListingOffer> =>
      this.post('/commerce/offers/', payload),

    /** POST /commerce/offers/:id/seller-respond/ */
    offerSellerRespond: (
      id: number | string,
      body: { action: 'accept' | 'decline' | 'counter'; amount?: number; note?: string },
    ): Promise<ListingOffer> => this.post(`/commerce/offers/${id}/seller-respond/`, body),

    /** POST /commerce/offers/:id/buyer-respond/ */
    offerBuyerRespond: (
      id: number | string,
      body: { action: 'accept' | 'decline' | 'counter'; amount?: number; note?: string },
    ): Promise<ListingOffer> => this.post(`/commerce/offers/${id}/buyer-respond/`, body),

    /** GET /commerce/wishlist/ */
    wishlist: (): Promise<unknown> => this.get('/commerce/wishlist/'),

    /** POST /commerce/wishlist/toggle/ */
    wishlistToggle: (payload: { listing_id: number | string }): Promise<{ success: boolean; added?: boolean; message?: string }> =>
      this.post('/commerce/wishlist/toggle/', payload),

    /** GET /commerce/orders/seller_stats/ */
    sellerStats: (): Promise<unknown> => this.get('/commerce/orders/seller_stats/'),

    /** POST /commerce/orders/request-withdrawal/ */
    requestWithdrawal: (payload: {
      amount: number | string;
      payout_method_id: number | string;
      seller_note?: string;
    }): Promise<unknown> =>
      this.post('/commerce/orders/request-withdrawal/', payload),

    /** GET /commerce/orders/withdrawal-requests/ */
    withdrawalRequests: (): Promise<unknown> => this.get('/commerce/orders/withdrawal-requests/'),

    /** GET /commerce/orders/seller_escrow/ */
    sellerEscrow: (): Promise<unknown> => this.get('/commerce/orders/seller_escrow/'),

    /** GET /commerce/orders/payouts/ */
    payouts: (params?: Record<string, string | number | boolean | null | undefined>): Promise<PaginatedResponse<Payout>> => 
      this.get('/commerce/orders/payouts/', params),

    /** POST /commerce/orders/process_payout/ */
    processPayout: (payoutId: number | string): Promise<Payout> =>
      this.post('/commerce/orders/process_payout/', { payout_id: payoutId }),
  };

  // ===========================================================================
  // MARKETPLACE ENDPOINTS
  // ===========================================================================

  marketplace = {
    /** GET /marketplace/stores/ */
    stores: (params?: Record<string, string | number | boolean | null | undefined>): Promise<PaginatedResponse<Store>> =>
      this.get('/marketplace/stores/', params),

    /** GET /marketplace/stores/:slug/ or /marketplace/stores/:id/ */
    storeDetail: (slugOrId: string | number): Promise<Store> =>
      this.get(`/marketplace/stores/${slugOrId}/`),

    /** POST /marketplace/stores/:id/follow/ */
    followStore: (id: number | string): Promise<{ following: boolean }> =>
      this.post(`/marketplace/stores/${id}/follow/`),

    /** POST /marketplace/stores/:id/unfollow/ */
    unfollowStore: (id: number | string): Promise<{ following: boolean }> =>
      this.post(`/marketplace/stores/${id}/unfollow/`),

    /** GET /marketplace/sellers/ */
    sellers: (params?: Record<string, string | number | boolean | null | undefined>): Promise<PaginatedResponse<User>> =>
      this.get('/marketplace/sellers/', params),

    /** GET /marketplace/sellers/:id/ */
    sellerDetail: (id: number | string): Promise<User> =>
      this.get(`/marketplace/sellers/${id}/`),

    /** GET /marketplace/favorites/ */
    favorites: (): Promise<{ favorites: Array<{ id: string; listing: Listing }> }> =>
      this.get('/marketplace/favorites/'),

    /** POST /marketplace/favorites/ */
    addFavorite: (payload: { listingId?: string | number; listing?: string | number }): Promise<unknown> =>
      this.post('/marketplace/favorites/', payload),

    /** DELETE /marketplace/favorites/:id/ */
    removeFavorite: (id: number | string): Promise<unknown> =>
      this.request(`/marketplace/favorites/${id}/`, { method: 'DELETE' }),

    /** GET /marketplace/items/ */
    items: (params?: Record<string, string | number | boolean | null | undefined>): Promise<PaginatedResponse<Listing>> =>
      this.get('/marketplace/items/', params),

    /** GET /marketplace/items/:id/ */
    itemDetail: (id: number | string): Promise<Listing> =>
      this.get(`/marketplace/items/${id}/`),

    /** GET /marketplace/payment-methods/ */
    paymentMethods: (): Promise<unknown> =>
      this.get('/marketplace/payment-methods/'),

    /** Seller payout preferences (CRUD) */
    sellerPaymentMethods: {
      list: (): Promise<unknown> => this.get('/marketplace/payment-methods/'),
      create: (payload: Record<string, unknown>): Promise<unknown> => this.post('/marketplace/payment-methods/', payload),
      update: (id: number | string, payload: Record<string, unknown>): Promise<unknown> =>
        this.patch(`/marketplace/payment-methods/${id}/`, payload),
      remove: (id: number | string): Promise<unknown> =>
        this.delete(`/marketplace/payment-methods/${id}/`),
    },
  };

  // ===========================================================================
  // SELLER ONBOARDING (versioned aliases of backend sellers app)
  // ===========================================================================

  sellers = {
    /** GET /sellers/onboarding/progress/ */
    onboardingProgress: (): Promise<unknown> => this.get('/sellers/onboarding/progress/'),

    storeSetup: (payload: {
      store_name: string;
      store_categories?: string[];
      store_category?: string;
      store_category_other?: string;
      store_location: string;
      store_description?: string;
      store_logo?: File | null;
      store_banner?: File | null;
      seller_type?: 'product' | 'service';
    }): Promise<unknown> => {
      const fd = new FormData();
      Object.entries(payload).forEach(([key, value]) => {
        if (value === undefined || value === null) return;
        if (key === 'store_categories' && Array.isArray(value)) {
          value.forEach(v => fd.append('store_categories', v));
        } else if (value instanceof File) {
          fd.append(key, value);
        } else {
          fd.append(key, String(value));
        }
      });
      return this.post('/sellers/store/setup/', fd);
    },

    /** POST /sellers/verification/identity/ (multipart) */
    submitIdentityVerification: (payload: {
      id_type: string;
      id_number: string;
      id_front_image: File;
      selfie_with_id: File;
    }): Promise<unknown> => {
      const fd = new FormData();
      fd.append('id_type', payload.id_type);
      fd.append('id_number', payload.id_number);
      fd.append('id_front_image', payload.id_front_image);
      fd.append('selfie_with_id', payload.selfie_with_id);
      return this.post('/sellers/verification/identity/', fd);
    },

    /** GET /sellers/verification/identity/status/ */
    identityVerificationStatus: (): Promise<unknown> =>
      this.get('/sellers/verification/identity/status/'),

    /** POST /sellers/verification/business/ (multipart) */
    submitBusinessVerification: (payload: {
      business_name: string;
      business_registration_no?: string;
      tin_number?: string;
      business_certificate?: File;
      bank_account_number?: string;
      bank_name?: string;
      bank_account_name?: string;
    }): Promise<unknown> => {
      const fd = new FormData();
      fd.append('business_name', payload.business_name);
      if (payload.business_registration_no) fd.append('business_registration_no', payload.business_registration_no);
      if (payload.tin_number) fd.append('tin_number', payload.tin_number);
      if (payload.business_certificate) fd.append('business_certificate', payload.business_certificate);
      if (payload.bank_account_number) fd.append('bank_account_number', payload.bank_account_number);
      if (payload.bank_name) fd.append('bank_name', payload.bank_name);
      if (payload.bank_account_name) fd.append('bank_account_name', payload.bank_account_name);
      return this.post('/sellers/verification/business/', fd);
    },

    /** Alias: POST /sellers/verification/identity/ (same as submitIdentityVerification) */
    identitySubmit: (payload: {
      id_type: string;
      id_number: string;
      id_front_image: File;
      selfie_with_id: File;
    }): Promise<any> => {
      const fd = new FormData();
      fd.append('id_type', payload.id_type);
      fd.append('id_number', payload.id_number);
      fd.append('id_front_image', payload.id_front_image);
      fd.append('selfie_with_id', payload.selfie_with_id);
      return this.post('/sellers/verification/identity/', fd);
    },

    /** POST /sellers/payout/add/ */
    payoutAdd: (payload: {
      account_type: string;
      account_number: string;
      account_name: string;
      bank_code?: string;
    }): Promise<{ message: string; payout_account_id: number }> =>
      this.post('/sellers/payout/add/', payload),

    /** POST /sellers/payout/verify/ */
    payoutVerify: (payload: {
      payout_account_id: number;
      verification_code: string;
    }): Promise<{ message: string }> =>
      this.post('/sellers/payout/verify/', payload),

    /** GET /sellers/admin/verifications/ */
    adminVerifications: (params?: Record<string, string | number | boolean | null | undefined>): Promise<any> =>
      this.get('/admin/sellers/', params),

    /** GET /admin/sellers/:id/ */
    adminSellerDetail: (id: number | string): Promise<any> =>
      this.get(`/admin/sellers/${id}/`),

    /** POST /admin/sellers/:id/identity/approve/ */
    adminVerifyApprove: (id: number | string): Promise<any> =>
      this.post(`/admin/sellers/${id}/identity/approve/`),

    /** POST /admin/sellers/:id/identity/reject/ */
    adminVerifyReject: (id: number | string, payload: { reason: string }): Promise<any> =>
      this.post(`/admin/sellers/${id}/identity/reject/`, payload),

    /** POST /admin/sellers/:id/verification/business/approve/ (admin) */
    adminVerifyBusinessApprove: (id: number | string): Promise<any> =>
      this.post(`/admin/sellers/${id}/verification/business/approve/`),

    /** POST /admin/sellers/:id/verification/business/reject/ (admin) */
    adminVerifyBusinessReject: (id: number | string, payload: { reason: string }): Promise<any> =>
      this.post(`/admin/sellers/${id}/verification/business/reject/`, payload),
  };

  // ===========================================================================
  // TRUST ENDPOINTS
  // ===========================================================================

  trust = {
    /** GET /trust/reviews/ */
    reviews: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<Review>> =>
      this.get('/trust/reviews/', params),

    /** GET /trust/reviews/listing_stats/?listing= */
    listingReviewStats: (
      listingId: string | number,
    ): Promise<{
      average_rating?: number;
      total_reviews?: number;
      recommend_percentage?: number | null;
      verified_purchase_count?: number;
      rating_distribution?: Record<number, number>;
    }> => this.get('/trust/reviews/listing_stats/', { listing: listingId }),

    /** POST /trust/reports/ */
    createReport: (payload: CreateReportPayload): Promise<Report> =>
      this.post('/trust/reports/', payload),

    /** GET /trust/reports/ (admin) */
    reports: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<Report>> =>
      this.get('/trust/reports/', params),

    /** POST /trust/reports/:id/resolve/ (admin) */
    resolveReport: (id: number | string, payload: { admin_notes?: string }): Promise<Report> =>
      this.post(`/trust/reports/${id}/resolve/`, payload),

    /** POST /trust/reports/:id/dismiss/ (admin) */
    dismissReport: (id: number | string, payload: { admin_notes?: string }): Promise<Report> =>
      this.post(`/trust/reports/${id}/dismiss/`, payload),

    /** GET /trust/anomalies/ (admin) */
    anomalies: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<unknown>> =>
      this.get('/trust/anomalies/', params),

    /** GET /trust/verifications/ (admin) */
    verifications: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<Verification>> =>
      this.get('/trust/verifications/', params),

    /** POST /trust/verifications/verify-id/ */
    verifyId: (file: File): Promise<Verification> => {
      const fd = new FormData();
      fd.append('id_document', file);
      return this.post('/trust/verifications/verify-id/', fd);
    },

    /** POST /trust/verifications/verify-tin/ */
    verifyTin: (file: File): Promise<Verification> => {
      const fd = new FormData();
      fd.append('tin_document', file);
      return this.post('/trust/verifications/verify-tin/', fd);
    },

    /** POST /trust/verifications/verify-license/ */
    verifyLicense: (file: File): Promise<Verification> => {
      const fd = new FormData();
      fd.append('license_document', file);
      return this.post('/trust/verifications/verify-license/', fd);
    },

    /** PATCH /trust/reviews/:id/ (seller_reply only) */
    replyReview: (id: number | string, payload: { seller_reply: string }): Promise<Review> =>
      this.patch(`/trust/reviews/${id}/`, payload),

    /** ── Admin Verification Actions ────────────────────────────────────────── */

    /** POST /trust/verifications/:id/verify_id/ (admin) */
    approveVerificationId: (id: number | string, payload: { status: 'approved' | 'rejected' | 'pending'; notes?: string }): Promise<void> =>
      this.post(`/trust/verifications/${id}/verify_id/`, payload),

    /** POST /trust/verifications/:id/verify_tin/ (admin) */
    approveVerificationTin: (id: number | string, payload: { status: 'approved' | 'rejected' | 'pending'; notes?: string }): Promise<void> =>
      this.post(`/trust/verifications/${id}/verify_tin/`, payload),

    /** POST /trust/verifications/:id/verify_license/ (admin) */
    approveVerificationLicense: (id: number | string, payload: { status: 'approved' | 'rejected' | 'pending'; notes?: string }): Promise<void> =>
      this.post(`/trust/verifications/${id}/verify_license/`, payload),
  };

  // ===========================================================================
  // COMMUNICATIONS ENDPOINTS
  // ===========================================================================

  communications = {
    /** GET /communications/conversations/ */
    conversations: (params?: Record<string, string | number | boolean | null | undefined>): Promise<PaginatedResponse<Conversation>> =>
      this.get('/communications/conversations/', params),

    /** GET /communications/conversations/:id/ */
    conversationDetail: (id: number | string): Promise<Conversation> =>
      this.get(`/communications/conversations/${id}/`),

    /** POST /communications/conversations/start_conversation/ */
    startConversation: (payload: {
      seller_id?: number | string;
      agent_id?: number | string;
      user_id?: number | string;
      listing_id?: number | string;
      order_id?: number | string;
      dispute_id?: number | string;
    }): Promise<Conversation> =>
      this.post('/communications/conversations/start_conversation/', payload),

    /** GET /communications/conversations/:id/messages/ */
    messages: (
      conversationId: number | string,
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<Message>> =>
      this.get(`/communications/conversations/${conversationId}/messages/`, params),

    /** POST /communications/conversations/:id/messages/ */
    sendMessage: (conversationId: number | string, payload: { text: string; attachment?: File }): Promise<Message> => {
      if (payload.attachment) {
        const fd = new FormData();
        fd.append('text', payload.text);
        fd.append('attachment', payload.attachment);
        return this.post(`/communications/conversations/${conversationId}/messages/`, fd);
      }
      return this.post(`/communications/conversations/${conversationId}/messages/`, {
        text: payload.text,
      });
    },

    /** POST /communications/conversations/:id/mark_read/ */
    markRead: (conversationId: number | string): Promise<{ success: boolean }> =>
      this.post(`/communications/conversations/${conversationId}/mark_read/`),

    /** GET /communications/conversations/unread_count/ */
    unreadCount: (): Promise<{ unread_count: number }> =>
      this.get('/communications/conversations/unread_count/'),

    /** GET /communications/notifications/ */
    notifications: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<Notification>> =>
      this.get('/communications/notifications/', params),

    /** GET /communications/support-requests/:id/ */
    supportRequestDetail: (id: number | string): Promise<SupportRequest> =>
      this.get(`/communications/support-requests/${id}/`),

    /** PATCH /communications/support-requests/:id/ */
    updateSupportRequest: (id: number | string, payload: UpdateSupportRequestPayload): Promise<SupportRequest> =>
      this.patch(`/communications/support-requests/${id}/`, payload),

    /** POST /communications/notifications/mark-all-read/ */
    markAllNotificationsRead: (): Promise<{ success: boolean }> =>
      this.post('/communications/notifications/mark-all-read/'),

    /** GET /communications/notifications/unread-count/ */
    notificationsUnreadCount: (): Promise<{ count: number }> =>
      this.get('/communications/notifications/unread-count/'),

    /** GET /communications/support-requests/ */
    supportRequests: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<SupportRequest>> =>
      this.get('/communications/support-requests/', params),

    /** POST /communications/support-requests/ */
    createSupportRequest: (payload: { subject: string; message: string; attachments?: File[] }): Promise<SupportRequest> => {
      if (payload.attachments && payload.attachments.length > 0) {
        const fd = new FormData();
        fd.append('subject', payload.subject);
        fd.append('message', payload.message);
        payload.attachments.forEach((f) => fd.append('attachments', f));
        return this.post('/communications/support-requests/', fd);
      }
      return this.post('/communications/support-requests/', {
        subject: payload.subject,
        message: payload.message,
      });
    },

    /** GET /communications/device-tokens/ */
    deviceTokens: (): Promise<PaginatedResponse<DeviceToken>> =>
      this.get('/communications/device-tokens/'),

    /** POST /communications/device-tokens/ */
    registerDeviceToken: (payload: { token: string; device_type: 'ios' | 'android' | 'web' }): Promise<DeviceToken> =>
      this.post('/communications/device-tokens/', payload),
  };

  // ===========================================================================
  // ESCROW ENDPOINTS
  // ===========================================================================

  escrow = {
    /** GET /escrow/transactions/ */
    transactions: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<Transaction>> =>
      this.get('/escrow/transactions/', params),

    /** POST /escrow/transactions/:id/confirm/ */
    confirmTransaction: (id: number | string): Promise<Transaction> =>
      this.post(`/escrow/transactions/${id}/confirm/`),

    /** POST /escrow/transactions/:id/release/ */
    releaseTransaction: (id: number | string): Promise<Transaction> =>
      this.post(`/escrow/transactions/${id}/release/`),

    /** POST /escrow/transactions/:id/refund/ */
    refundTransaction: (id: number | string, payload?: { reason?: string }): Promise<Transaction> =>
      this.post(`/escrow/transactions/${id}/refund/`, payload),

    // Payment links live under /escrow/pay/links/*
    createPayLink: (payload: CreatePayLinkPayload): Promise<PayLink> =>
      this.post('/escrow/pay/links/', payload),
    payLinkDetail: (token: string): Promise<Record<string, unknown>> =>
      this.get<Record<string, unknown>>(`/escrow/pay/links/${token}/`, undefined, {
        skipAuth: true,
      }),
    payLinkRequestOtp: (token: string, payload: { phone: string }): Promise<{ detail?: string }> =>
      this.post(`/escrow/pay/links/${token}/request-otp/`, payload, { skipAuth: true }),
    payLinkVerifyOtp: (
      token: string,
      payload: { phone: string; otp: string },
    ): Promise<{ detail?: string }> =>
      this.post(`/escrow/pay/links/${token}/verify-otp/`, payload, { skipAuth: true }),
    payLinkPay: (
      token: string,
      payload: { payment_method?: string; payment_channel?: string; buyer_phone?: string; buyer_name?: string; redirect_url?: string; cancel_url?: string }
    ): Promise<{
      payment_url?: string;
      success: boolean;
      error?: string;
      transaction_reference?: string;
    }> => this.post(`/escrow/pay/links/${token}/pay/`, payload, { skipAuth: true }),

    /** GET /escrow/disputes/ */
    disputes: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<Dispute>> =>
      this.get('/escrow/disputes/', params),

    /** GET /escrow/disputes/:id/ */
    disputeDetail: (id: number | string): Promise<Dispute> =>
      this.get(`/escrow/disputes/${id}/`),

    /** POST /escrow/disputes/:id/respond/ (multipart) */
    respondDispute: (
      id: number | string,
      payload: {
        notes?: string;
        evidence_video?: File;
        evidence_images?: File[];
      },
    ): Promise<Dispute> => {
      const fd = new FormData();
      if (payload.notes) fd.append('notes', payload.notes);
      if (payload.evidence_video) fd.append('evidence_video', payload.evidence_video);
      if (payload.evidence_images) {
        payload.evidence_images.forEach((f) => fd.append('evidence_images', f));
      }
      return this.post(`/escrow/disputes/${id}/respond/`, fd);
    },

    /** POST /escrow/disputes/:id/resolve/ (admin) */
    resolveDispute: (id: number | string, payload: ResolveDisputePayload): Promise<Dispute> =>
      this.post(`/escrow/disputes/${id}/resolve/`, payload),
  };

  // ===========================================================================
  // INSIGHTS ENDPOINTS
  // ===========================================================================

  insights = {
    /** GET /insights/admin-stats/ */
    adminStats: (): Promise<AdminStats> =>
      this.get('/insights/admin-stats/'),

    /** GET /insights/platform-metrics/ */
    platformMetrics: (): Promise<PlatformMetrics> =>
      this.get('/insights/platform-metrics/'),

    /** GET /insights/user-growth/ (charts; other growth endpoints exist too) */
    growthCharts: (params?: { period?: string }): Promise<GrowthCharts> =>
      this.get('/insights/user-growth/', params),

    /** GET /insights/seller-stats-summary/ */
    sellerStatsSummary: (): Promise<unknown> =>
      this.get('/insights/seller-stats-summary/'),

    /** GET /insights/seller-stats/ */
    sellerStats: (): Promise<unknown> =>
      this.get('/insights/seller-stats/'),
  };

  // ===========================================================================
  // FEATURES ENDPOINTS
  // ===========================================================================

  features = {
    featuresList: (): Promise<PaginatedResponse<Feature>> =>
      this.get('/features/features/'),

    plansList: (): Promise<PaginatedResponse<Plan>> =>
      this.get('/features/plans/'),

    currentSubscription: (): Promise<Subscription> =>
      this.get('/features/subscriptions/current/'),
  };

  // ===========================================================================
  // ACCOUNTS ADMIN ENDPOINTS
  // ===========================================================================

  accounts = {
    /** GET /accounts/users/ (admin) */
    users: (
      params?: Record<string, string | number | boolean | null | undefined>,
    ): Promise<PaginatedResponse<User>> =>
      this.get('/accounts/users/', params),

    /** POST /accounts/users/:id/toggle_seller_status/ (admin) */
    toggleSellerStatus: (id: number | string): Promise<unknown> =>
      this.post(`/accounts/users/${id}/toggle_seller_status/`),

    /** POST /accounts/users/:id/toggle_active_status/ (admin) */
    toggleActiveStatus: (id: number | string): Promise<unknown> =>
      this.post(`/accounts/users/${id}/toggle_active_status/`),

    /** GET /accounts/users/stats/ (admin) */
    userStats: (): Promise<unknown> =>
      this.get('/accounts/users/stats/'),
  };
}

// =============================================================================
// Singleton Export
// =============================================================================

export const api = new ApiClient();
export default api;

// Re-export error class for convenience
export { ApiClientError };
