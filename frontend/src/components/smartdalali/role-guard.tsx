'use client';

import { useEffect } from 'react';
import { toast } from 'sonner';
import { useAuthStore, useUIStore } from '@/store';
import { canAccessAdminPortal, canAccessSellerPortal } from '@/lib/auth-roles';

export type RoleGuardKind = 'admin' | 'seller';

interface RoleGuardProps {
  kind: RoleGuardKind;
  children: React.ReactNode;
}

export function RoleGuard({ kind, children }: RoleGuardProps) {
  const { user, isAuthenticated, isLoading } = useAuthStore();
  const { navigate } = useUIStore();

  useEffect(() => {
    if (isLoading) return;

    if (!isAuthenticated || !user) {
      navigate({ view: 'login' });
      return;
    }

    if (kind === 'admin' && !canAccessAdminPortal(user)) {
      toast.error('You do not have access to the admin area.');
      navigate({ view: 'home' });
      return;
    }

    if (kind === 'seller' && !canAccessSellerPortal(user)) {
      toast.error('Seller access is required for this area.');
      navigate({ view: 'seller-register' });
    }
  }, [kind, isAuthenticated, user, isLoading, navigate]);

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
