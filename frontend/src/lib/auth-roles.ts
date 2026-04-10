import type { User } from '@/types/api';
import type { AppView, ViewName } from '@/store/ui-store';

/**
 * Mirrors backend `IsAdmin`: superuser or staff (`backend/core/permissions.py`).
 * Note: JWT `role` is only `'admin'` for superusers (`accounts/roles.get_user_role`);
 * staff without superuser still need `is_staff` to use admin APIs.
 */
export function canAccessAdminPortal(user: User | null | undefined): boolean {
  if (!user) return false;
  if (user.is_superuser || user.is_staff) return true;
  return user.role === 'admin';
}

/**
 * Mirrors backend `IsSeller`: superuser, `seller` group, or active SellerProfile.
 */
export function canAccessSellerPortal(user: User | null | undefined): boolean {
  if (!user) return false;
  if (user.is_superuser) return true;
  if (user.is_seller) return true;
  const sp = user.seller_profile;
  if (sp && typeof sp === 'object' && 'is_active' in sp && sp.is_active) return true;
  return false;
}

/** Where to land after login / OTP verify once `user` is hydrated from `/accounts/me/`. */
export function getPostLoginView(user: User | null | undefined): ViewName {
  if (!user) return 'home';
  if (canAccessAdminPortal(user)) return 'admin-dashboard';
  if (canAccessSellerPortal(user)) return 'seller-dashboard';
  return 'home';
}

/** Typed `AppView` for `navigate()` (no route params on these destinations). */
export function getPostLoginAppView(user: User | null | undefined): AppView {
  const v = getPostLoginView(user);
  switch (v) {
    case 'admin-dashboard':
      return { view: 'admin-dashboard' };
    case 'seller-dashboard':
      return { view: 'seller-dashboard' };
    default:
      return { view: 'home' };
  }
}
