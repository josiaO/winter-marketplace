import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// =============================================================================
// ViewName — exhaustive list of every SPA "route"
// =============================================================================

export type ViewName =
  // ── Public / Auth ─────────────────────────────────────────────────────────
  | 'home'
  | 'login'
  | 'register'
  | 'otp-verify'
  | 'forgot-password'
  | 'reset-password'
  // ── Browsing ──────────────────────────────────────────────────────────────
  | 'category'
  | 'product'
  | 'store'
  | 'seller-profile'
  | 'search'
  // ── Commerce ──────────────────────────────────────────────────────────────
  | 'cart'
  | 'checkout'
  | 'payment-confirmation'
  | 'payment-return'
  | 'checkout-success'
  // ── Buyer Account ─────────────────────────────────────────────────────────
  | 'orders'
  | 'order-detail'
  | 'wishlist'
  // ── Communication ─────────────────────────────────────────────────────────
  | 'messages'
  | 'conversation'
  | 'notifications'
  | 'support'
  // ── Account Settings ──────────────────────────────────────────────────────
  | 'profile'
  | 'change-password'
  | 'delete-account'
  // ── Seller Portal ─────────────────────────────────────────────────────────
  | 'seller-register'
  | 'seller-dashboard'
  | 'seller-listings'
  | 'seller-listing-create'
  | 'seller-listing-edit'
  | 'seller-orders'
  | 'seller-payouts'
  | 'seller-escrow'
  | 'seller-verification'
  | 'seller-payment-method'
  // ── Admin Panel ───────────────────────────────────────────────────────────
  | 'admin-dashboard'
  | 'admin-users'
  | 'admin-verifications'
  | 'admin-listings'
  | 'admin-reports'
  | 'admin-disputes'
  | 'admin-payouts'
  | 'admin-plans'
  | 'admin-analytics'
  | 'admin-catalog';

// =============================================================================
// ViewMap — each view's required parameters (use Record<string, never> for none)
// =============================================================================

interface ViewMap {
  // ── Public / Auth ─────────────────────────────────────────────────────────
  home: {};
  login: {};
  register: {};
  'otp-verify': { email: string };
  'forgot-password': {};
  'reset-password': { uid: string; token: string };

  // ── Browsing ──────────────────────────────────────────────────────────────
  category: { slug: string };
  product: { id: string };
  store: { slug: string };
  'seller-profile': { id: string };
  search: { query: string };

  // ── Commerce ──────────────────────────────────────────────────────────────
  cart: {};
  checkout: {};
  'payment-confirmation': { orderId: string };
  'payment-return': { reference?: string };
  'checkout-success': { orderId: string };

  // ── Buyer Account ─────────────────────────────────────────────────────────
  orders: {};
  'order-detail': { id: string };
  wishlist: {};

  // ── Communication ─────────────────────────────────────────────────────────
  messages: {};
  conversation: { id: string };
  notifications: {};
  support: {};

  // ── Account Settings ──────────────────────────────────────────────────────
  profile: {};
  'change-password': {};
  'delete-account': {};

  // ── Seller Portal ─────────────────────────────────────────────────────────
  'seller-register': {};
  'seller-dashboard': {};
  'seller-listings': {};
  'seller-listing-create': {};
  'seller-listing-edit': { id: string };
  'seller-orders': {};
  'seller-payouts': {};
  'seller-escrow': {};
  'seller-verification': {};
  'seller-payment-method': {};

  // ── Admin Panel ───────────────────────────────────────────────────────────
  'admin-dashboard': {};
  'admin-users': {};
  'admin-verifications': {};
  'admin-listings': {};
  'admin-reports': {};
  'admin-disputes': {};
  'admin-payouts': {};
  'admin-plans': {};
  'admin-analytics': {};
  'admin-catalog': {};
}

// =============================================================================
// AppView — discriminated union:  { view: ViewName } & ViewMap[ViewName]
// =============================================================================

export type AppView = { [K in ViewName]: { view: K } & ViewMap[K] }[ViewName];

// =============================================================================
// Store
// =============================================================================

interface UIStore {
  /** The current SPA "page" */
  currentView: AppView;
  /** Global search query (synced with header input) */
  searchQuery: string;
  /** Currently selected category slug / id for filtering */
  selectedCategory: string | null;

  /** Navigate to a new view */
  navigate: (view: AppView) => void;
  /** Update the global search query */
  setSearchQuery: (query: string) => void;
  /** Set / clear the selected category filter */
  setSelectedCategory: (category: string | null) => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      currentView: { view: 'home' },
      searchQuery: '',
      selectedCategory: null,

      navigate: (currentView) => set({ currentView }),

      setSearchQuery: (searchQuery) => set({ searchQuery }),

      setSelectedCategory: (selectedCategory) => set({ selectedCategory }),
    }),
    {
      name: 'smartdalali-ui',
      // Persist only lightweight filter state — never persist currentView
      // so the user always lands on "home" after a fresh page load.
      partialize: (state) => ({
        searchQuery: state.searchQuery,
        selectedCategory: state.selectedCategory,
      }),
    }
  )
);
