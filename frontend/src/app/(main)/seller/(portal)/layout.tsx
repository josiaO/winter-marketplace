'use client';

import { RoleGuard } from '@/components/smartdalali/role-guard';
import { SellerSidebar } from '@/components/smartdalali/seller-sidebar';
import { Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { useState } from 'react';

export default function SellerPortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  return (
    <RoleGuard kind="seller">
      <div className="flex h-screen overflow-hidden bg-background">
        {/* Desktop Sidebar */}
        <div className="hidden lg:block h-full">
          <SellerSidebar />
        </div>

        {/* Mobile Header & Sidebar */}
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <header className="lg:hidden flex items-center h-16 px-4 border-b bg-card">
            <Sheet open={isMobileOpen} onOpenChange={setIsMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="mr-2">
                  <Menu className="w-6 h-6" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="p-0 w-64 border-r-0">
                <SheetHeader className="sr-only">
                  <SheetTitle>Seller navigation</SheetTitle>
                </SheetHeader>
                <SellerSidebar />
              </SheetContent>
            </Sheet>
            <span className="font-bold text-lg">Seller Portal</span>
          </header>

          <main className="flex-1 relative overflow-y-auto scrollbar-hide">
            <div className="max-w-7xl mx-auto p-4 md:p-8">
              {children}
            </div>
          </main>
        </div>
      </div>
    </RoleGuard>
  );
}
