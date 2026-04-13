'use client';

import dynamic from 'next/dynamic';

/**
 * Code-split view entry points for the App Router.
 * Mirrors the previous `page.tsx` dynamic imports (no SSR for these client-heavy screens).
 */
export const HomePageView = dynamic(
  () => import('@/views/home-page').then((m) => m.HomePage),
  { ssr: false },
);
export const LoginPageView = dynamic(
  () => import('@/views/login-page').then((m) => m.LoginPage),
  { ssr: false },
);
export const RegisterPageView = dynamic(
  () => import('@/views/register-page').then((m) => m.RegisterPage),
  { ssr: false },
);
export const OtpVerifyPageView = dynamic(
  () => import('@/views/otp-verify-page').then((m) => m.OtpVerifyPage),
  { ssr: false },
);
export const ForgotPasswordPageView = dynamic(
  () => import('@/views/forgot-password-page').then((m) => m.ForgotPasswordPage),
  { ssr: false },
);
export const ResetPasswordPageView = dynamic(
  () => import('@/views/reset-password-page').then((m) => m.ResetPasswordPage),
  { ssr: false },
);
export const ChangePasswordPageView = dynamic(
  () => import('@/views/change-password-page').then((m) => m.ChangePasswordPage),
  { ssr: false },
);
export const DeleteAccountPageView = dynamic(
  () => import('@/views/delete-account-page').then((m) => m.DeleteAccountPage),
  { ssr: false },
);

export const CategoryPageView = dynamic(
  () => import('@/views/category-page').then((m) => m.CategoryPage),
  { ssr: false },
);
export const ProductPageView = dynamic(
  () => import('@/views/product-page').then((m) => m.ProductPage),
  { ssr: false },
);
export const StorePageView = dynamic(
  () => import('@/views/store-page').then((m) => m.StorePage),
  { ssr: false },
);
export const SellerProfilePageView = dynamic(
  () => import('@/views/seller-profile-page').then((m) => m.SellerProfilePage),
  { ssr: false },
);
export const SearchPageView = dynamic(
  () => import('@/views/search-page').then((m) => m.SearchPage),
  { ssr: false },
);

export const CartPageView = dynamic(
  () => import('@/views/cart-page').then((m) => m.CartPage),
  { ssr: false },
);
export const CheckoutPageView = dynamic(
  () => import('@/views/checkout-page').then((m) => m.CheckoutPage),
  { ssr: false },
);
export const PaymentConfirmationPageView = dynamic(
  () => import('@/views/payment-confirmation').then((m) => m.PaymentConfirmationPage),
  { ssr: false },
);
export const PaymentReturnPageView = dynamic(
  () => import('@/views/payment-return-page').then((m) => m.PaymentReturnPage),
  { ssr: false },
);
export const CheckoutSuccessPageView = dynamic(
  () => import('@/views/checkout-success').then((m) => m.CheckoutSuccessPage),
  { ssr: false },
);

export const GuestPayLinkPageView = dynamic(
  () => import('@/views/guest-pay-link-page').then((m) => m.GuestPayLinkPage),
  { ssr: false },
);

export const OrdersPageView = dynamic(
  () => import('@/views/orders-page').then((m) => m.OrdersPage),
  { ssr: false },
);
export const OrderDetailPageView = dynamic(
  () => import('@/views/order-detail').then((m) => m.OrderDetailPage),
  { ssr: false },
);
export const WishlistPageView = dynamic(
  () => import('@/views/wishlist-page').then((m) => m.WishlistPage),
  { ssr: false },
);

export const MessagesPageView = dynamic(
  () => import('@/views/messages-page').then((m) => m.MessagesPage),
  { ssr: false },
);
export const ConversationPageView = dynamic(
  () => import('@/views/conversation-page').then((m) => m.ConversationPage),
  { ssr: false },
);
export const NotificationsPageView = dynamic(
  () => import('@/views/notifications-page').then((m) => m.NotificationsPage),
  { ssr: false },
);
export const SupportPageView = dynamic(
  () => import('@/views/support-page').then((m) => m.SupportPage),
  { ssr: false },
);

export const ProfilePageView = dynamic(
  () => import('@/views/profile-page').then((m) => m.ProfilePage),
  { ssr: false },
);
export const SellerRegisterPageView = dynamic(
  () => import('@/views/seller-register').then((m) => m.SellerRegisterPage),
  { ssr: false },
);
export const SellerDashboardPageView = dynamic(
  () => import('@/views/seller-dashboard').then((m) => m.SellerDashboardPage),
  { ssr: false },
);
export const SellerListingsPageView = dynamic(
  () => import('@/views/seller-listings').then((m) => m.SellerListingsPage),
  { ssr: false },
);
export const SellerListingCreatePageView = dynamic(
  () => import('@/views/seller-listing-create').then((m) => m.SellerListingCreatePage),
  { ssr: false },
);
export const SellerListingEditPageView = dynamic(
  () => import('@/views/seller-listing-edit').then((m) => m.SellerListingEditPage),
  { ssr: false },
);
export const SellerOrdersPageView = dynamic(
  () => import('@/views/seller-orders').then((m) => m.SellerOrdersPage),
  { ssr: false },
);
export const SellerPayoutsPageView = dynamic(
  () => import('@/views/seller-payouts').then((m) => m.SellerPayoutsPage),
  { ssr: false },
);
export const SellerEscrowPageView = dynamic(
  () => import('@/views/seller-escrow').then((m) => m.SellerEscrowPage),
  { ssr: false },
);
export const SellerVerificationPageView = dynamic(
  () => import('@/views/seller-verification').then((m) => m.SellerVerificationPage),
  { ssr: false },
);
export const SellerPaymentMethodPageView = dynamic(
  () => import('@/views/seller-payment-method').then((m) => m.SellerPaymentMethodPage),
  { ssr: false },
);

export const SellerStoreSetupPageView = dynamic(
  () => import('@/views/seller-store-setup').then((m) => m.SellerStoreSetupPage),
  { ssr: false },
);
export const SellerVerifyIdentityPageView = dynamic(
  () => import('@/views/seller-verify-identity').then((m) => m.SellerVerifyIdentityPage),
  { ssr: false },
);
export const SellerAddPayoutPageView = dynamic(
  () => import('@/views/seller-add-payout').then((m) => m.SellerAddPayoutPage),
  { ssr: false },
);
export const SellerOrderDetailPageView = dynamic(
  () => import('@/views/seller-order-detail').then((m) => m.SellerOrderDetailPage),
  { ssr: false },
);
export const SellerWalletPageView = dynamic(
  () => import('@/views/seller-wallet').then((m) => m.SellerWalletPage),
  { ssr: false },
);
export const SellerWithdrawPageView = dynamic(
  () => import('@/views/seller-withdraw').then((m) => m.SellerWithdrawPage),
  { ssr: false },
);
export const SellerAnalyticsPageView = dynamic(
  () => import('@/views/seller-analytics').then((m) => m.SellerAnalyticsPage),
  { ssr: false },
);
export const SellerReviewsPageView = dynamic(
  () => import('@/views/seller-reviews').then((m) => m.SellerReviewsPage),
  { ssr: false },
);

export const AdminDashboardPageView = dynamic(
  () => import('@/views/admin-dashboard').then((m) => m.AdminDashboardPage),
  { ssr: false },
);
export const AdminUsersPageView = dynamic(
  () => import('@/views/admin-users').then((m) => m.AdminUsersPage),
  { ssr: false },
);
export const AdminVerificationsPageView = dynamic(
  () => import('@/views/admin-verifications').then((m) => m.AdminVerificationsPage),
  { ssr: false },
);
export const AdminListingsPageView = dynamic(
  () => import('@/views/admin-listings').then((m) => m.AdminListingsPage),
  { ssr: false },
);
export const AdminReportsPageView = dynamic(
  () => import('@/views/admin-reports').then((m) => m.AdminReportsPage),
  { ssr: false },
);
export const AdminDisputesPageView = dynamic(
  () => import('@/views/admin-disputes').then((m) => m.AdminDisputesPage),
  { ssr: false },
);
export const AdminPayoutsPageView = dynamic(
  () => import('@/views/admin-payouts').then((m) => m.AdminPayoutsPage),
  { ssr: false },
);
export const AdminPlansPageView = dynamic(
  () => import('@/views/admin-plans').then((m) => m.AdminPlansPage),
  { ssr: false },
);
export const AdminAnalyticsPageView = dynamic(
  () => import('@/views/admin-analytics').then((m) => m.AdminAnalyticsPage),
  { ssr: false },
);
export const AdminCatalogPageView = dynamic(
  () => import('@/views/admin-catalog').then((m) => m.AdminCatalogPage),
  { ssr: false },
);
