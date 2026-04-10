'use client';

import { RoleGuard } from '@/components/smartdalali/role-guard';

export default function SellerPortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <RoleGuard kind="seller">{children}</RoleGuard>;
}
