'use client';

import { RoleGuard } from '@/components/smartdalali/role-guard';

export default function AdminSectionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <RoleGuard kind="admin">{children}</RoleGuard>;
}
