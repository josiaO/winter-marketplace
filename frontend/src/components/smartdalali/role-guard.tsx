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
  const { user, isAuthenticated, isLoading, isHydrated } = useAuthStore();
  const router = useRouter();

  useEffect(() => {
    if (!isHydrated) return;

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
  }, [kind, isHydrated, isAuthenticated, user, isLoading, router]);

  // We only block if the storage hasn't been rehydrated yet. 
  // We no longer block on background profile syncing (isLoading) because 
  // components have their own internal loading states and can handle partial user data.
  if (!isHydrated) {
    return (
      <div className="min-h-[50vh] flex items-center justify-center text-sm text-muted-foreground">
        <div className="flex flex-col items-center gap-2">
          <div className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span>Initializing…</span>
        </div>
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
