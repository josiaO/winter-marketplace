'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { useAuthStore } from '@/store';
import { canAccessAdminPortal, canAccessSellerPortal } from '@/lib/auth-roles';
import { routes } from '@/lib/routes';

export type RoleGuardKind = 'admin' | 'seller';

interface RoleGuardProps {
  kind: RoleGuardKind;
  children: React.ReactNode;
}

export function RoleGuard({ kind, children }: RoleGuardProps) {
  const { user, isAuthenticated, isLoading } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated || !user) {
      router.replace(routes.login());
      return;
    }

    if (kind === 'admin' && !canAccessAdminPortal(user)) {
      toast.error('You do not have access to the admin area.');
      router.replace(routes.home());
      return;
    }

    if (kind === 'seller' && !canAccessSellerPortal(user)) {
      toast.error('Seller access is required for this area.');
      router.replace(routes.sellerRegister());
    }
  }, [kind, isAuthenticated, user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return null;
  }

  if (kind === 'admin' && !canAccessAdminPortal(user)) {
    return null;
  }

  if (kind === 'seller' && !canAccessSellerPortal(user)) {
    return null;
  }

  return <>{children}</>;
}
