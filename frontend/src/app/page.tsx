'use client';

import { useEffect } from 'react';
import { useUIStore } from '@/store';
import dynamic from 'next/dynamic';
import { RoleGuard } from '@/components/smartdalali/role-guard';

/**
 * IMPORTANT PERF FIX:
 * This app is currently a SPA with a view-switcher. If we statically import all views,
 * webpack bundles buyer/seller/admin pages into the initial chunk, making first load very slow.
 * We dynamically import each view so only the current view's code is loaded.
 */

const SiteHeader = dynamic(() => import('@/components/smartdalali').then((m) => m.SiteHeader), { ssr: false });
const SiteFooter = dynamic(() => import('@/components/smartdalali').then((m) => m.SiteFooter), { ssr: false });

const HomePage = dynamic(() => import('@/views/home-page').then((m) => m.HomePage), { ssr: false });
const LoginPage = dynamic(() => import('@/views/login-page').then((m) => m.LoginPage), { ssr: false });
const RegisterPage = dynamic(() => import('@/views/register-page').then((m) => m.RegisterPage), { ssr: false });
const OtpVerifyPage = dynamic(() => import('@/views/otp-verify-page').then((m) => m.OtpVerifyPage), { ssr: false });
const ForgotPasswordPage = dynamic(() => import('@/views/forgot-password-page').then((m) => m.ForgotPasswordPage), { ssr: false });
const ResetPasswordPage = dynamic(() => import('@/views/reset-password-page').then((m) => m.ResetPasswordPage), { ssr: false });
const ChangePasswordPage = dynamic(() => import('@/views/change-password-page').then((m) => m.ChangePasswordPage), { ssr: false });
const DeleteAccountPage = dynamic(() => import('@/views/delete-account-page').then((m) => m.DeleteAccountPage), { ssr: false });

const CategoryPage = dynamic(() => import('@/views/category-page').then((m) => m.CategoryPage), { ssr: false });
const ProductPage = dynamic(() => import('@/views/product-page').then((m) => m.ProductPage), { ssr: false });
const StorePage = dynamic(() => import('@/views/store-page').then((m) => m.StorePage), { ssr: false });
const SellerProfilePage = dynamic(() => import('@/views/seller-profile-page').then((m) => m.SellerProfilePage), { ssr: false });
const SearchPage = dynamic(() => import('@/views/search-page').then((m) => m.SearchPage), { ssr: false });

const CartPage = dynamic(() => import('@/views/cart-page').then((m) => m.CartPage), { ssr: false });
const CheckoutPage = dynamic(() => import('@/views/checkout-page').then((m) => m.CheckoutPage), { ssr: false });
const PaymentConfirmationPage = dynamic(() => import('@/views/payment-confirmation').then((m) => m.PaymentConfirmationPage), { ssr: false });
const PaymentReturnPage = dynamic(() => import('@/views/payment-return-page').then((m) => m.PaymentReturnPage), { ssr: false });
const CheckoutSuccessPage = dynamic(() => import('@/views/checkout-success').then((m) => m.CheckoutSuccessPage), { ssr: false });

const OrdersPage = dynamic(() => import('@/views/orders-page').then((m) => m.OrdersPage), { ssr: false });
const OrderDetailPage = dynamic(() => import('@/views/order-detail').then((m) => m.OrderDetailPage), { ssr: false });
const WishlistPage = dynamic(() => import('@/views/wishlist-page').then((m) => m.WishlistPage), { ssr: false });

const MessagesPage = dynamic(() => import('@/views/messages-page').then((m) => m.MessagesPage), { ssr: false });
const ConversationPage = dynamic(() => import('@/views/conversation-page').then((m) => m.ConversationPage), { ssr: false });
const NotificationsPage = dynamic(() => import('@/views/notifications-page').then((m) => m.NotificationsPage), { ssr: false });
const SupportPage = dynamic(() => import('@/views/support-page').then((m) => m.SupportPage), { ssr: false });

const ProfilePage = dynamic(() => import('@/views/profile-page').then((m) => m.ProfilePage), { ssr: false });
const SellerRegisterPage = dynamic(() => import('@/views/seller-register').then((m) => m.SellerRegisterPage), { ssr: false });
const SellerDashboardPage = dynamic(() => import('@/views/seller-dashboard').then((m) => m.SellerDashboardPage), { ssr: false });
const SellerListingsPage = dynamic(() => import('@/views/seller-listings').then((m) => m.SellerListingsPage), { ssr: false });
const SellerListingCreatePage = dynamic(() => import('@/views/seller-listing-create').then((m) => m.SellerListingCreatePage), { ssr: false });
const SellerListingEditPage = dynamic(() => import('@/views/seller-listing-edit').then((m) => m.SellerListingEditPage), { ssr: false });
const SellerOrdersPage = dynamic(() => import('@/views/seller-orders').then((m) => m.SellerOrdersPage), { ssr: false });
const SellerPayoutsPage = dynamic(() => import('@/views/seller-payouts').then((m) => m.SellerPayoutsPage), { ssr: false });
const SellerEscrowPage = dynamic(() => import('@/views/seller-escrow').then((m) => m.SellerEscrowPage), { ssr: false });
const SellerVerificationPage = dynamic(() => import('@/views/seller-verification').then((m) => m.SellerVerificationPage), { ssr: false });
const SellerPaymentMethodPage = dynamic(() => import('@/views/seller-payment-method').then((m) => m.SellerPaymentMethodPage), { ssr: false });

const AdminDashboardPage = dynamic(() => import('@/views/admin-dashboard').then((m) => m.AdminDashboardPage), { ssr: false });
const AdminUsersPage = dynamic(() => import('@/views/admin-users').then((m) => m.AdminUsersPage), { ssr: false });
const AdminVerificationsPage = dynamic(() => import('@/views/admin-verifications').then((m) => m.AdminVerificationsPage), { ssr: false });
const AdminListingsPage = dynamic(() => import('@/views/admin-listings').then((m) => m.AdminListingsPage), { ssr: false });
const AdminReportsPage = dynamic(() => import('@/views/admin-reports').then((m) => m.AdminReportsPage), { ssr: false });
const AdminDisputesPage = dynamic(() => import('@/views/admin-disputes').then((m) => m.AdminDisputesPage), { ssr: false });
const AdminPayoutsPage = dynamic(() => import('@/views/admin-payouts').then((m) => m.AdminPayoutsPage), { ssr: false });
const AdminPlansPage = dynamic(() => import('@/views/admin-plans').then((m) => m.AdminPlansPage), { ssr: false });
const AdminAnalyticsPage = dynamic(() => import('@/views/admin-analytics').then((m) => m.AdminAnalyticsPage), { ssr: false });
const AdminCatalogPage = dynamic(() => import('@/views/admin-catalog').then((m) => m.AdminCatalogPage), { ssr: false });

export default function Home() {
  const { currentView, navigate } = useUIStore();

  /** After hosted checkout, gateway redirects here with ref in query — do not trust status params. */
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const ref =
      params.get('transaction_reference') ||
      params.get('ref') ||
      params.get('reference');
    if (ref) {
      navigate({ view: 'payment-return', reference: ref });
      window.history.replaceState({}, '', window.location.pathname || '/');
    }
  }, [navigate]);

  const renderView = () => {
    switch (currentView.view) {
      case 'home':
        return <HomePage />;
      case 'login':
        return <LoginPage />;
      case 'register':
        return <RegisterPage />;
      case 'otp-verify':
        return <OtpVerifyPage />;
      case 'forgot-password':
        return <ForgotPasswordPage />;
      case 'reset-password':
        return <ResetPasswordPage />;
      case 'change-password':
        return <ChangePasswordPage />;
      case 'delete-account':
        return <DeleteAccountPage />;
      case 'category':
        return <CategoryPage />;
      case 'product':
        return <ProductPage />;
      case 'store':
        return <StorePage />;
      case 'seller-profile':
        return <SellerProfilePage />;
      case 'cart':
        return <CartPage />;
      case 'checkout':
        return <CheckoutPage />;
      case 'payment-confirmation':
        return <PaymentConfirmationPage />;
      case 'checkout-success':
        return <CheckoutSuccessPage />;
      case 'orders':
        return <OrdersPage />;
      case 'order-detail':
        return <OrderDetailPage />;
      case 'search':
        return <SearchPage />;
      case 'seller-register':
        return <SellerRegisterPage />;
      case 'profile':
        return <ProfilePage />;
      case 'seller-dashboard':
        return (
          <RoleGuard kind="seller">
            <SellerDashboardPage />
          </RoleGuard>
        );
      case 'seller-listings':
        return (
          <RoleGuard kind="seller">
            <SellerListingsPage />
          </RoleGuard>
        );
      case 'seller-orders':
        return (
          <RoleGuard kind="seller">
            <SellerOrdersPage />
          </RoleGuard>
        );
      case 'seller-payouts':
        return (
          <RoleGuard kind="seller">
            <SellerPayoutsPage />
          </RoleGuard>
        );
      case 'wishlist':
        return <WishlistPage />;
      case 'messages':
        return <MessagesPage />;
      case 'conversation':
        return <ConversationPage />;
      case 'notifications':
        return <NotificationsPage />;
      case 'support':
        return <SupportPage />;
      case 'seller-listing-create':
        return (
          <RoleGuard kind="seller">
            <SellerListingCreatePage />
          </RoleGuard>
        );
      case 'seller-listing-edit':
        return (
          <RoleGuard kind="seller">
            <SellerListingEditPage />
          </RoleGuard>
        );
      case 'seller-escrow':
        return (
          <RoleGuard kind="seller">
            <SellerEscrowPage />
          </RoleGuard>
        );
      case 'seller-verification':
        return (
          <RoleGuard kind="seller">
            <SellerVerificationPage />
          </RoleGuard>
        );
      case 'seller-payment-method':
        return (
          <RoleGuard kind="seller">
            <SellerPaymentMethodPage />
          </RoleGuard>
        );
      case 'admin-dashboard':
        return (
          <RoleGuard kind="admin">
            <AdminDashboardPage />
          </RoleGuard>
        );
      case 'admin-users':
        return (
          <RoleGuard kind="admin">
            <AdminUsersPage />
          </RoleGuard>
        );
      case 'admin-verifications':
        return (
          <RoleGuard kind="admin">
            <AdminVerificationsPage />
          </RoleGuard>
        );
      case 'admin-listings':
        return (
          <RoleGuard kind="admin">
            <AdminListingsPage />
          </RoleGuard>
        );
      case 'admin-reports':
        return (
          <RoleGuard kind="admin">
            <AdminReportsPage />
          </RoleGuard>
        );
      case 'admin-disputes':
        return (
          <RoleGuard kind="admin">
            <AdminDisputesPage />
          </RoleGuard>
        );
      case 'admin-payouts':
        return (
          <RoleGuard kind="admin">
            <AdminPayoutsPage />
          </RoleGuard>
        );
      case 'admin-plans':
        return (
          <RoleGuard kind="admin">
            <AdminPlansPage />
          </RoleGuard>
        );
      case 'admin-analytics':
        return (
          <RoleGuard kind="admin">
            <AdminAnalyticsPage />
          </RoleGuard>
        );
      case 'admin-catalog':
        return (
          <RoleGuard kind="admin">
            <AdminCatalogPage />
          </RoleGuard>
        );
      case 'payment-return':
        return <PaymentReturnPage />;
      default:
        return <HomePage />;
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <SiteHeader />
      <main className="flex-1">{renderView()}</main>
      <SiteFooter />
    </div>
  );
}
