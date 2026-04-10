'use client';

import { useState, useEffect, useRef } from 'react';
import {
  ShoppingBag,
  Search,
  Menu,
  X,
  User,
  LogOut,
  Package,
  LayoutDashboard,
  Store,
  ChevronDown,
  Home,
  Grid3X3,
  CreditCard,
  ClipboardList,
  Wallet,
  Heart,
  MessageSquare,
  Bell,
  Shield,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetClose,
} from '@/components/ui/sheet';
import { useUIStore, useAuthStore, useCartStore } from '@/store';
import { api } from '@/lib/api-client';
import { cn } from '@/lib/utils';
import { getInitials } from '@/lib/helpers';
import { AppView } from '@/types';
import type { Category } from '@/types/api';
import { canAccessAdminPortal, canAccessSellerPortal } from '@/lib/auth-roles';

/** Derive display name from Django User (first_name + last_name || username) */
function userDisplayName(user: {
  first_name: string;
  last_name: string;
  username: string;
}): string {
  return (user.first_name + ' ' + user.last_name).trim() || user.username;
}

export function SiteHeader() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [isCategoryOpen, setIsCategoryOpen] = useState(false);
  const categoryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const { navigate, searchQuery, setSearchQuery, currentView } = useUIStore();
  const { user, isAuthenticated, logout } = useAuthStore();
  const { itemCount } = useCartStore();

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 8);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    // Fetch categories on mount
    async function loadCategories() {
      try {
        const res = await api.catalog.categories({ tree: true });
        const cats = Array.isArray(res) ? res : res.results || [];
        setCategories(cats);
      } catch {
        // Categories will load empty
      }
    }
    loadCategories();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate({ view: 'search', query: searchQuery.trim() });
      setIsMobileMenuOpen(false);
    }
  };

  const handleCategoryHover = () => {
    if (categoryTimeoutRef.current) {
      clearTimeout(categoryTimeoutRef.current);
    }
    setIsCategoryOpen(true);
  };

  const handleCategoryLeave = () => {
    categoryTimeoutRef.current = setTimeout(() => {
      setIsCategoryOpen(false);
    }, 200);
  };

  const handleLogout = () => {
    logout();
    navigate({ view: 'home' });
  };

  const isActive = (view: string) => currentView.view === view;

  return (
    <>
      <header
        className={cn(
          'sticky top-0 z-50 w-full transition-all duration-300 bg-background/95 backdrop-blur-md border-b',
          isScrolled ? 'shadow-md' : 'shadow-sm',
        )}
      >
        {/* Top bar */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Left: Logo + Mobile menu */}
            <div className="flex items-center gap-3">
              {/* Mobile hamburger */}
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                onClick={() => setIsMobileMenuOpen(true)}
                aria-label="Open menu"
              >
                <Menu className="w-5 h-5" />
              </Button>

              {/* Logo */}
              <button
                onClick={() => navigate({ view: 'home' })}
                className="flex items-center gap-2 group"
              >
                <div className="w-9 h-9 bg-primary rounded-xl flex items-center justify-center group-hover:scale-105 transition-transform">
                  <ShoppingBag className="w-5 h-5 text-primary-foreground" />
                </div>
                <div className="hidden sm:block">
                  <span className="text-lg font-bold text-foreground tracking-tight">
                    Smart<span className="text-primary">Dalali</span>
                  </span>
                </div>
              </button>
            </div>

            {/* Center: Search bar (desktop) */}
            <div className="hidden md:flex flex-1 max-w-xl mx-6">
              <form onSubmit={handleSearch} className="w-full relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  ref={searchInputRef}
                  type="search"
                  placeholder="Search products, brands, categories..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 h-10 rounded-full bg-muted/50 border-transparent focus:border-primary focus:bg-background transition-colors"
                />
              </form>
            </div>

            {/* Right: Navigation + User + Cart */}
            <div className="flex items-center gap-1 sm:gap-2">
              {/* Desktop nav links */}
              <nav className="hidden lg:flex items-center gap-1">
                <Button
                  variant={isActive('home') ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => navigate({ view: 'home' })}
                  className="rounded-full text-sm font-medium"
                >
                  <Home className="w-4 h-4 mr-1.5" />
                  Home
                </Button>

                {/* Categories dropdown */}
                <div
                  className="relative"
                  onMouseEnter={handleCategoryHover}
                  onMouseLeave={handleCategoryLeave}
                >
                  <Button
                    variant="ghost"
                    size="sm"
                    className="rounded-full text-sm font-medium"
                    onClick={() => {
                      navigate({ view: 'home' });
                    }}
                  >
                    <Grid3X3 className="w-4 h-4 mr-1.5" />
                    Categories
                    <ChevronDown className="w-3.5 h-3.5 ml-1" />
                  </Button>

                  {isCategoryOpen && categories.length > 0 && (
                    <div className="absolute top-full left-0 pt-2 w-56">
                      <div className="rounded-xl border bg-popover shadow-lg p-2">
                        {categories.map((cat) => (
                          <button
                            key={cat.id}
                            onClick={() => {
                              navigate({ view: 'category', slug: cat.slug });
                              setIsCategoryOpen(false);
                            }}
                            className="w-full text-left px-3 py-2 text-sm rounded-lg hover:bg-muted transition-colors flex items-center justify-between"
                          >
                            <span>{cat.name}</span>
                            {cat.listing_count > 0 && (
                              <span className="text-xs text-muted-foreground">
                                {cat.listing_count}
                              </span>
                            )}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    if (user && canAccessSellerPortal(user)) {
                      navigate({ view: 'seller-dashboard' });
                    } else if (isAuthenticated) {
                      navigate({ view: 'seller-register' });
                    } else {
                      navigate({ view: 'login' });
                    }
                  }}
                  className="rounded-full text-sm font-medium"
                >
                  <Store className="w-4 h-4 mr-1.5" />
                  Sell
                </Button>
              </nav>

              {/* Cart button */}
              <Button
                variant="ghost"
                size="icon"
                className="relative rounded-full"
                onClick={() => navigate({ view: 'cart' })}
                aria-label="Shopping cart"
              >
                <ShoppingBag className="w-5 h-5" />
                {itemCount > 0 && (
                  <Badge className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 text-[10px] font-bold bg-primary text-primary-foreground rounded-full">
                    {itemCount > 99 ? '99+' : itemCount}
                  </Badge>
                )}
              </Button>

              {/* User menu */}
              {isAuthenticated && user ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      className="rounded-full p-0 h-9 w-9 relative"
                    >
                      <Avatar className="h-9 w-9">
                        <AvatarImage
                          src={user.avatar || undefined}
                          alt={userDisplayName(user)}
                        />
                        <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">
                          {getInitials(userDisplayName(user))}
                        </AvatarFallback>
                      </Avatar>
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56 rounded-xl">
                    <div className="px-3 py-2">
                      <p className="text-sm font-medium">
                        {userDisplayName(user)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {user.email}
                      </p>
                      {user.is_verified && (
                        <Badge
                          variant="secondary"
                          className="mt-1 text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                        >
                          Verified
                        </Badge>
                      )}
                    </div>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => navigate({ view: 'orders' })}>
                      <Package className="w-4 h-4 mr-2" />
                      My Orders
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => navigate({ view: 'wishlist' })}>
                      <Heart className="w-4 h-4 mr-2" />
                      Wishlist
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => navigate({ view: 'messages' })}>
                      <MessageSquare className="w-4 h-4 mr-2" />
                      Messages
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => navigate({ view: 'notifications' })}>
                      <Bell className="w-4 h-4 mr-2" />
                      Notifications
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() => navigate({ view: 'profile' })}
                    >
                      <User className="w-4 h-4 mr-2" />
                      My Profile
                    </DropdownMenuItem>
                    {canAccessSellerPortal(user) && (
                      <>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => navigate({ view: 'seller-dashboard' })}
                        >
                          <LayoutDashboard className="w-4 h-4 mr-2" />
                          Seller Dashboard
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => navigate({ view: 'seller-listings' })}
                        >
                          <ClipboardList className="w-4 h-4 mr-2" />
                          My Listings
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => navigate({ view: 'seller-orders' })}
                        >
                          <CreditCard className="w-4 h-4 mr-2" />
                          Seller Orders
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => navigate({ view: 'seller-payouts' })}
                        >
                          <Wallet className="w-4 h-4 mr-2" />
                          Payouts
                        </DropdownMenuItem>
                      </>
                    )}
                    {canAccessAdminPortal(user) && (
                      <>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => navigate({ view: 'admin-dashboard' })}
                        >
                          <Shield className="w-4 h-4 mr-2" />
                          Admin Panel
                        </DropdownMenuItem>
                      </>
                    )}
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={handleLogout}
                      className="text-red-600 dark:text-red-400"
                    >
                      <LogOut className="w-4 h-4 mr-2" />
                      Logout
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : (
                <div className="hidden sm:flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigate({ view: 'login' })}
                    className="rounded-full text-sm font-medium"
                  >
                    Login
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => navigate({ view: 'register' })}
                    className="rounded-full text-sm font-medium"
                  >
                    Register
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Mobile Menu Sheet */}
      <Sheet open={isMobileMenuOpen} onOpenChange={setIsMobileMenuOpen}>
        <SheetContent side="left" className="w-80 p-0">
          <SheetHeader className="p-4 pb-3 border-b">
            <div className="flex items-center justify-between">
              <SheetTitle className="flex items-center gap-2">
                <div className="w-8 h-8 bg-primary rounded-xl flex items-center justify-center">
                  <ShoppingBag className="w-4 h-4 text-primary-foreground" />
                </div>
                <span className="text-lg font-bold">
                  Smart<span className="text-primary">Dalali</span>
                </span>
              </SheetTitle>
              <SheetClose asChild>
                <Button variant="ghost" size="icon" className="rounded-full">
                  <X className="w-4 h-4" />
                </Button>
              </SheetClose>
            </div>
          </SheetHeader>

          {/* Mobile search */}
          <div className="px-4 py-3 border-b">
            <form onSubmit={handleSearch} className="w-full relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                type="search"
                placeholder="Search products..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 h-10 rounded-full bg-muted/50 border-transparent"
              />
            </form>
          </div>

          {/* Navigation */}
          <nav className="flex flex-col p-2">
            <SheetClose asChild>
              <button
                onClick={() => navigate({ view: 'home' })}
                className={cn(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  isActive('home')
                    ? 'bg-primary/10 text-primary'
                    : 'text-foreground hover:bg-muted',
                )}
              >
                <Home className="w-4 h-4" />
                Home
              </button>
            </SheetClose>

            {/* Categories section */}
            {categories.length > 0 && (
              <div className="mt-1">
                <p className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Categories
                </p>
                {categories.slice(0, 6).map((cat) => (
                  <SheetClose key={cat.id} asChild>
                    <button
                      onClick={() =>
                        navigate({ view: 'category', slug: cat.slug })
                      }
                      className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm hover:bg-muted transition-colors text-foreground"
                    >
                      <span className="font-medium">{cat.name}</span>
                      {cat.listing_count > 0 && (
                        <span className="ml-auto text-xs text-muted-foreground">
                          {cat.listing_count}
                        </span>
                      )}
                    </button>
                  </SheetClose>
                ))}
              </div>
            )}

            <div className="border-t my-2" />

            <SheetClose asChild>
              <button
                onClick={() => {
                  if (user && canAccessSellerPortal(user)) {
                    navigate({ view: 'seller-dashboard' });
                  } else if (isAuthenticated) {
                    navigate({ view: 'seller-register' });
                  } else {
                    navigate({ view: 'login' });
                  }
                }}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-foreground hover:bg-muted transition-colors"
              >
                <Store className="w-4 h-4" />
                Sell on SmartDalali
              </button>
            </SheetClose>

            {isAuthenticated && user ? (
              <>
                <div className="border-t my-2" />
                <p className="px-3 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Account
                </p>
                <SheetClose asChild>
                  <button
                    onClick={() => navigate({ view: 'orders' })}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm hover:bg-muted transition-colors text-foreground w-full"
                  >
                    <Package className="w-4 h-4" />
                    My Orders
                  </button>
                </SheetClose>
                <SheetClose asChild>
                  <button
                    onClick={() => navigate({ view: 'wishlist' })}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm hover:bg-muted transition-colors text-foreground w-full"
                  >
                    <Heart className="w-4 h-4" />
                    Wishlist
                  </button>
                </SheetClose>
                <SheetClose asChild>
                  <button
                    onClick={() => navigate({ view: 'messages' })}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm hover:bg-muted transition-colors text-foreground w-full"
                  >
                    <MessageSquare className="w-4 h-4" />
                    Messages
                  </button>
                </SheetClose>
                <SheetClose asChild>
                  <button
                    onClick={() => navigate({ view: 'notifications' })}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm hover:bg-muted transition-colors text-foreground w-full"
                  >
                    <Bell className="w-4 h-4" />
                    Notifications
                  </button>
                </SheetClose>
                <SheetClose asChild>
                  <button
                    onClick={() => navigate({ view: 'profile' })}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm hover:bg-muted transition-colors text-foreground w-full"
                  >
                    <User className="w-4 h-4" />
                    My Profile
                  </button>
                </SheetClose>
                {canAccessSellerPortal(user) && (
                  <SheetClose asChild>
                    <button
                      onClick={() => navigate({ view: 'seller-dashboard' })}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm hover:bg-muted transition-colors text-foreground w-full"
                    >
                      <LayoutDashboard className="w-4 h-4" />
                      Seller Dashboard
                    </button>
                  </SheetClose>
                )}
                {canAccessAdminPortal(user) && (
                  <SheetClose asChild>
                    <button
                      onClick={() => navigate({ view: 'admin-dashboard' })}
                      className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm hover:bg-muted transition-colors text-foreground w-full"
                    >
                      <Shield className="w-4 h-4" />
                      Admin Panel
                    </button>
                  </SheetClose>
                )}
                <SheetClose asChild>
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors text-red-600 dark:text-red-400 w-full"
                  >
                    <LogOut className="w-4 h-4" />
                    Logout
                  </button>
                </SheetClose>
              </>
            ) : (
              <>
                <div className="border-t my-2" />
                <div className="flex gap-2 px-3 py-2">
                  <SheetClose asChild>
                    <Button
                      variant="outline"
                      className="flex-1 rounded-full"
                      onClick={() => navigate({ view: 'login' })}
                    >
                      Login
                    </Button>
                  </SheetClose>
                  <SheetClose asChild>
                    <Button
                      className="flex-1 rounded-full"
                      onClick={() => navigate({ view: 'register' })}
                    >
                      Register
                    </Button>
                  </SheetClose>
                </div>
              </>
            )}
          </nav>
        </SheetContent>
      </Sheet>
    </>
  );
}
