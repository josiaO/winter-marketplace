'use client';

import { useEffect } from 'react';
import dynamic from 'next/dynamic';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { routes } from '@/lib/routes';

const SiteHeader = dynamic(
  () => import('@/components/smartdalali').then((m) => m.SiteHeader),
  { ssr: false },
);
const SiteFooter = dynamic(
  () => import('@/components/smartdalali').then((m) => m.SiteFooter),
  { ssr: false },
);

/**
 * Hosted checkout gateways redirect to site root with reference query params.
 * Normalize to the dedicated return route so refresh/share stays on one URL.
 */
function GatewayReturnRedirect() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (pathname !== '/') return;
    const ref =
      searchParams.get('transaction_reference') ||
      searchParams.get('ref') ||
      searchParams.get('reference');
    if (!ref) return;
    router.replace(routes.checkoutPaymentReturn(ref));
  }, [pathname, router, searchParams]);

  return null;
}

export function ShopShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-background">
      <GatewayReturnRedirect />
      <SiteHeader />
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </div>
  );
}
