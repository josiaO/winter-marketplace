import { Suspense } from 'react';
import { ShopShell } from './shop-shell';

export default function MainAppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <ShopShell>{children}</ShopShell>
    </Suspense>
  );
}
