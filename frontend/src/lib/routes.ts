/**
 * Canonical URL builders for the App Router.
 * Use these with `router.push` / `<Link href={...}>` so paths stay consistent.
 */
export const routes = {
  home: () => '/',

  login: () => '/login',
  register: () => '/register',
  registerVerify: (email: string) =>
    `/register/verify?email=${encodeURIComponent(email)}`,
  forgotPassword: () => '/forgot-password',
  resetPassword: (uid: string, token: string) =>
    `/reset-password?uid=${encodeURIComponent(uid)}&token=${encodeURIComponent(token)}`,

  accountPassword: () => '/account/password',
  accountDelete: () => '/account/delete',

  category: (slug: string) => `/categories/${encodeURIComponent(slug)}`,
  product: (id: string) => `/products/${encodeURIComponent(id)}`,
  store: (slug: string) => `/stores/${encodeURIComponent(slug)}`,
  sellerProfile: (id: string) => `/sellers/${encodeURIComponent(id)}`,

  /** Browse all listings or search via `?q=` (DRF `search` param is wired from this). */
  marketplace: (query?: string) => {
    const q = (query ?? '').trim();
    if (!q) return '/marketplace';
    return `/marketplace?q=${encodeURIComponent(q)}`;
  },

  cart: () => '/cart',
  checkout: () => '/checkout',
  checkoutConfirm: (orderId: string) =>
    `/checkout/confirm/${encodeURIComponent(orderId)}`,
  checkoutPaymentReturn: (reference?: string) => {
    if (!reference) return '/checkout/payment-return';
    return `/checkout/payment-return?reference=${encodeURIComponent(reference)}`;
  },
  checkoutSuccess: (orderId: string) =>
    `/checkout/success/${encodeURIComponent(orderId)}`,

  orders: () => '/orders',
  order: (id: string) => `/orders/${encodeURIComponent(id)}`,
  wishlist: () => '/wishlist',

  messages: () => '/messages',
  messageThread: (conversationId: string) =>
    `/messages/${encodeURIComponent(conversationId)}`,

  notifications: () => '/notifications',
  support: () => '/support',
  profile: () => '/profile',

  sellerRegister: () => '/seller/register',
  sellerDashboard: () => '/seller/dashboard',
  sellerListings: () => '/seller/listings',
  sellerListingNew: () => '/seller/listings/new',
  sellerListingEdit: (id: string) =>
    `/seller/listings/${encodeURIComponent(id)}/edit`,
  sellerOrders: () => '/seller/orders',
  sellerPayouts: () => '/seller/payouts',
  sellerEscrow: () => '/seller/escrow',
  sellerVerification: () => '/seller/verification',
  sellerPaymentMethod: () => '/seller/payment-method',
  
  sellerOnboardingStoreSetup: () => '/seller/onboarding/store-setup',
  sellerOnboardingVerifyIdentity: () => '/seller/onboarding/verify-identity',
  sellerOnboardingAddPayout: () => '/seller/onboarding/add-payout',

  adminDashboard: () => '/admin/dashboard',
  adminUsers: () => '/admin/users',
  adminVerifications: () => '/admin/verifications',
  adminListings: () => '/admin/listings',
  adminReports: () => '/admin/reports',
  adminDisputes: () => '/admin/disputes',
  adminPayouts: () => '/admin/payouts',
  adminPlans: () => '/admin/plans',
  adminAnalytics: () => '/admin/analytics',
  adminCatalog: () => '/admin/catalog',
} as const;

/** First segment after `/` for header active states (and similar). */
export type TopLevelNavKey =
  | 'home'
  | 'marketplace'
  | 'cart'
  | 'categories'
  | 'products'
  | 'stores'
  | 'sellers'
  | 'orders'
  | 'messages'
  | 'seller'
  | 'admin'
  | 'login'
  | 'register'
  | 'profile'
  | 'checkout'
  | 'account'
  | 'wishlist'
  | 'notifications'
  | 'support'
  | 'forgot-password'
  | 'reset-password';

export function topLevelNavFromPathname(pathname: string): TopLevelNavKey {
  const p = pathname === '/' ? '' : pathname.replace(/^\//, '');
  const seg = p.split('/')[0] ?? '';
  switch (seg) {
    case '':
      return 'home';
    case 'marketplace':
      return 'marketplace';
    case 'search':
      return 'marketplace';
    case 'cart':
      return 'cart';
    case 'categories':
      return 'categories';
    case 'products':
      return 'products';
    case 'stores':
      return 'stores';
    case 'sellers':
      return 'sellers';
    case 'orders':
      return 'orders';
    case 'messages':
      return 'messages';
    case 'seller':
      return 'seller';
    case 'admin':
      return 'admin';
    case 'login':
      return 'login';
    case 'register':
      return 'register';
    case 'profile':
      return 'profile';
    case 'checkout':
      return 'checkout';
    case 'account':
      return 'account';
    case 'wishlist':
      return 'wishlist';
    case 'notifications':
      return 'notifications';
    case 'support':
      return 'support';
    case 'forgot-password':
      return 'forgot-password';
    case 'reset-password':
      return 'reset-password';
    default:
      return 'home';
  }
}
