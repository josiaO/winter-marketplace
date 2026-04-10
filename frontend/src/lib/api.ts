const API_BASE = '';

async function apiFetch<T = unknown>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || `Request failed with status ${res.status}`);
  }

  return res.json();
}

export const api = {
  // Auth
  register: (data: { email: string; password: string; username: string; name?: string; phone?: string }) =>
    apiFetch('/api/auth/register', { method: 'POST', body: JSON.stringify(data) }),

  login: (data: { email: string; password: string }) =>
    apiFetch('/api/auth/login', { method: 'POST', body: JSON.stringify(data) }),

  // Listings
  getListings: (params?: Record<string, string | number | undefined>) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== '') {
          searchParams.set(key, String(value));
        }
      });
    }
    const qs = searchParams.toString();
    return apiFetch(`/api/listings${qs ? `?${qs}` : ''}`);
  },

  getListing: (id: string) => apiFetch(`/api/listings/${id}`),

  // Categories
  getCategories: () => apiFetch('/api/categories'),

  // Cart
  getCart: (userId: string) => apiFetch(`/api/cart?userId=${userId}`),
  addToCart: (data: { userId: string; listingId: string; quantity?: number }) =>
    apiFetch('/api/cart/add-item', { method: 'POST', body: JSON.stringify(data) }),
  removeFromCart: (data: { userId: string; cartItemId: string }) =>
    apiFetch('/api/cart/remove-item', { method: 'POST', body: JSON.stringify(data) }),
  updateCartQuantity: (data: { userId: string; cartItemId: string; quantity: number }) =>
    apiFetch('/api/cart/update-quantity', { method: 'POST', body: JSON.stringify(data) }),

  // Checkout
  checkout: (data: {
    userId: string;
    shippingAddress: string;
    shippingPhone: string;
    shippingMethod: string;
    paymentMethod: string;
  }) => apiFetch('/api/checkout', { method: 'POST', body: JSON.stringify(data) }),

  // Orders
  getOrders: (params: Record<string, string>) => {
    const searchParams = new URLSearchParams(params);
    return apiFetch(`/api/orders?${searchParams.toString()}`);
  },
  getOrder: (id: string) => apiFetch(`/api/orders/${id}`),
  cancelOrder: (id: string, data: { reason: string }) =>
    apiFetch(`/api/orders/${id}/cancel`, { method: 'POST', body: JSON.stringify(data) }),
  shipOrder: (id: string, data: { trackingNumber: string }) =>
    apiFetch(`/api/orders/${id}/ship`, { method: 'POST', body: JSON.stringify(data) }),
  deliverOrder: (id: string, data: Record<string, unknown> = {}) =>
    apiFetch(`/api/orders/${id}/deliver`, { method: 'POST', body: JSON.stringify(data) }),

  // Payments
  initiatePayment: (data: { orderId: string; paymentMethod: string }) =>
    apiFetch('/api/payments/initiate', { method: 'POST', body: JSON.stringify(data) }),
  confirmPayment: (data: { transactionId: string; providerRef: string }) =>
    apiFetch('/api/payments/confirm', { method: 'POST', body: JSON.stringify(data) }),
  getTransaction: (id: string) => apiFetch(`/api/payments/transactions/${id}`),

  // Reviews
  getReviews: (listingId: string) => apiFetch(`/api/reviews?listingId=${listingId}`),
  createReview: (data: { listingId: string; rating: number; title?: string; comment?: string }) =>
    apiFetch('/api/reviews', { method: 'POST', body: JSON.stringify(data) }),

  // Sellers
  registerSeller: (data: {
    userId: string;
    businessName: string;
    businessAddress?: string;
    bankName?: string;
    bankAccount?: string;
    bio?: string;
  }) => apiFetch('/api/sellers/register', { method: 'POST', body: JSON.stringify(data) }),
  getSellerDashboard: (userId: string) => apiFetch(`/api/sellers/dashboard?userId=${userId}`),
  getSellerListings: (userId: string) => apiFetch(`/api/sellers/listings?userId=${userId}`),
  getSellerPayouts: (userId: string) => apiFetch(`/api/sellers/payouts?userId=${userId}`),

  // Profile
  updateProfile: (data: {
    name?: string;
    phone?: string;
    bio?: string;
    avatar?: string;
  }) => apiFetch('/api/profile', { method: 'PATCH', body: JSON.stringify(data) }),

  // Seed
  seedData: () => apiFetch('/api/seed', { method: 'POST' }),
};
