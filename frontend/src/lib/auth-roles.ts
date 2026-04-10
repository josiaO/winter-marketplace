import type { User } from '@/types/api';
import { routes } from '@/lib/routes';

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
export function getPostLoginPath(user: User | null | undefined): string {
  if (!user) return routes.home();
  if (canAccessAdminPortal(user)) return routes.adminDashboard();
  if (canAccessSellerPortal(user)) return routes.sellerDashboard();
  return routes.home();
}
