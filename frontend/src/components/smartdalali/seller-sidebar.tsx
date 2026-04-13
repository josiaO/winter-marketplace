'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  LayoutDashboard,
  Package,
  ShoppingCart,
  Wallet,
  MessageSquare,
  Settings,
  ChevronLeft,
  ChevronRight,
  Store,
  ExternalLink,
  ShieldCheck,
  AlertCircle,
  BarChart3,
  Star,
  Landmark,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { routes } from '@/lib/routes';
import { useAuthStore } from '@/store';
import { Badge } from '@/components/ui/badge';
import { useState } from 'react';

interface SidebarItem {
  title: string;
  href: string;
  icon: any;
  badge?: string | number;
}

export function SellerSidebar() {
  const pathname = usePathname();
  const { user } = useAuthStore();
  const [isCollapsed, setIsCollapsed] = useState(false);

  const menuItems: SidebarItem[] = [
    { title: 'Dashboard', href: routes.sellerDashboard(), icon: LayoutDashboard },
    { title: 'My Listings', href: routes.sellerListings(), icon: Package },
    { title: 'Orders', href: routes.sellerOrders(), icon: ShoppingCart },
    { title: 'Wallet', href: routes.sellerWallet(), icon: Wallet },
    { title: 'Analytics', href: routes.sellerAnalytics(), icon: BarChart3 },
    { title: 'Reviews', href: routes.sellerReviews(), icon: Star },
    { title: 'Payouts', href: routes.sellerPayouts(), icon: Landmark },
    { title: 'Messages', href: routes.messages(), icon: MessageSquare },
    { title: 'Settings', href: routes.sellerSettings(), icon: Settings },
  ];

  const isActive = (href: string) => pathname === href;

  return (
    <div
      className={cn(
        'relative flex flex-col h-full bg-card border-r transition-all duration-300',
        isCollapsed ? 'w-20' : 'w-64'
      )}
    >
      {/* Header / Brand */}
      <div className="flex items-center justify-between h-16 px-4 border-b">
        {!isCollapsed && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <Store className="w-5 h-5 text-primary-foreground" />
            </div>
            <span className="font-bold text-lg">Seller Portal</span>
          </div>
        )}
        {isCollapsed && (
          <div className="w-8 h-8 bg-primary rounded-lg mx-auto flex items-center justify-center">
            <Store className="w-5 h-5 text-primary-foreground" />
          </div>
        )}
      </div>

      {/* Seller Info Quick View */}
      {!isCollapsed && user?.is_seller && (
        <div className="px-4 py-6 border-b">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <Store className="w-5 h-5 text-primary" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate">
                {user.seller_profile?.store_name || 'My Store'}
              </p>
              <div className="flex items-center gap-1 mt-0.5">
                {user.seller_profile?.verification_status === 'verified' ? (
                  <Badge variant="secondary" className="h-4 px-1 text-[10px] bg-green-100 text-green-700 hover:bg-green-100">
                    <ShieldCheck className="w-2.5 h-2.5 mr-0.5" />
                    Verified
                  </Badge>
                ) : (
                  <Badge variant="secondary" className="h-4 px-1 text-[10px] bg-amber-100 text-amber-700 hover:bg-amber-100">
                    <AlertCircle className="w-2.5 h-2.5 mr-0.5" />
                    Pending
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {menuItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              'flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors',
              isActive(item.href)
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-primary/10 hover:text-primary'
            )}
          >
            <item.icon className="w-5 h-5 shrink-0" />
            {!isCollapsed && (
              <span className="flex-1 truncate">{item.title}</span>
            )}
            {!isCollapsed && item.badge && (
              <Badge variant="secondary" className="ml-auto bg-primary/20 text-primary">
                {item.badge}
              </Badge>
            )}
          </Link>
        ))}
      </nav>

      {/* Secondary Actions */}
      <div className="px-2 py-4 border-t space-y-1">
        {!isCollapsed && (
          <p className="px-3 mb-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            Marketplace
          </p>
        )}
        <Link
           href={user?.seller_profile?.store_slug ? routes.storeView(user.seller_profile.store_slug) : routes.home()}
           target="_blank"
           className={cn(
             'flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium text-muted-foreground hover:bg-primary/10 hover:text-primary transition-colors'
           )}
        >
          <ExternalLink className="w-5 h-5 shrink-0" />
          {!isCollapsed && <span className="flex-1 truncate">View Public Store</span>}
        </Link>
      </div>

      {/* Collapse Toggle */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="absolute -right-3 top-20 w-6 h-6 bg-background border rounded-full flex items-center justify-center shadow-sm hover:bg-muted"
      >
        {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
      </button>
    </div>
  );
}
