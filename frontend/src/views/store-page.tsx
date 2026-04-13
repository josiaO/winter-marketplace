'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import {
  Home,
  Package,
  ShieldCheck,
  Store,
  Users,
  ShoppingBag,
  MapPin,
  LayoutGrid,
  List,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import { ProductCard } from '@/components/smartdalali/product-card';
import { SkeletonGrid } from '@/components/smartdalali/skeleton-grid';
import { EmptyState } from '@/components/smartdalali/empty-state';
import { useAuthStore, useUIStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatDate, normalizeMediaUrl } from '@/lib/helpers';
import { toast } from 'sonner';
import type { Listing, Store as StoreType } from '@/types/api';

export function StorePage({ storeSlug }: { storeSlug: string }) {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const { browseLayout, browseDensity, setBrowseLayout } = useUIStore();
  const slug = storeSlug;

  const [store, setStore] = useState<StoreType | null>(null);
  const [listings, setListings] = useState<Listing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isFollowing, setIsFollowing] = useState(false);
  const [isTogglingFollow, setIsTogglingFollow] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [totalCount, setTotalCount] = useState(0);

  // Fetch store detail
  useEffect(() => {
    if (!slug) return;
    setIsLoading(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });

    api.marketplace
      .storeDetail(slug)
      .then((data) => {
        setStore(data);
        setIsFollowing(data.is_followed || false);
      })
      .catch(() => {
        toast.error('Failed to load store');
      })
      .finally(() => setIsLoading(false));
  }, [slug]);

  // Fetch store listings
  useEffect(() => {
    if (!slug) return;
    api.marketplace
      .items({ store: slug, page })
      .then((res) => {
        const items = res.results || [];
        setListings((prev) => (page === 1 ? items : [...prev, ...items]));
        setTotalCount(res.count || 0);
        setHasMore(!!res.next);
      })
      .catch(() => setListings([]));
  }, [slug, page]);

  const handleFollow = useCallback(async () => {
    if (!isAuthenticated) {
      toast.error('Please login to follow stores');
      return;
    }
    if (!store) return;
    setIsTogglingFollow(true);
    try {
      if (isFollowing) {
        await api.marketplace.unfollowStore(store.id);
      } else {
        await api.marketplace.followStore(store.id);
      }
      setIsFollowing(!isFollowing);
      toast.success(isFollowing ? 'Unfollowed store' : 'Now following store');
    } catch {
      toast.error('Failed to update follow status');
    } finally {
      setIsTogglingFollow(false);
    }
  }, [isAuthenticated, store, isFollowing]);

  const handleProductSelect = useCallback(
    (listing: Listing) => router.push(routes.product(String(listing.id))),
    [router]
  );

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-4 w-48 mb-6" />
        <Skeleton className="h-40 w-full rounded-2xl mb-4" />
        <div className="flex items-center gap-4 mb-8">
          <Skeleton className="h-20 w-20 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64" />
          </div>
        </div>
        <SkeletonGrid />
      </div>
    );
  }

  if (!store) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <EmptyState
          icon={Store}
          title="Store not found"
          description="The store you're looking for doesn't exist or has been removed."
          actionLabel="Go Home"
          onAction={() => router.push(routes.home())}
        />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Breadcrumb */}
      <Breadcrumb className="mb-6">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink
              className="cursor-pointer text-sm flex items-center gap-1"
              onClick={() => router.push(routes.home())}
            >
              <Home className="w-3.5 h-3.5" />
              Home
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage className="text-sm font-medium">{store.name}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {/* Store Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        {/* Cover Image */}
        {store.cover && (
          <div className="relative w-full h-40 sm:h-56 rounded-2xl overflow-hidden bg-muted mb-4">
            <Image
              src={normalizeMediaUrl(store.cover) || store.cover}
              alt={`${store.name} cover`}
              fill
              className="object-cover"
              priority
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" />
          </div>
        )}

        {/* Store Info */}
        <div className="flex flex-col sm:flex-row items-start sm:items-end gap-4 -mt-12 sm:-mt-8 relative z-10 px-4 sm:px-6">
          {/* Logo */}
          <div className="relative">
            <Avatar className="h-20 w-20 sm:h-24 sm:w-24 border-4 border-background rounded-2xl">
              <AvatarImage src={store.logo || undefined} alt={store.name} />
              <AvatarFallback className="text-xl font-bold bg-emerald-100 text-emerald-700 rounded-2xl">
                {store.name.charAt(0)}
              </AvatarFallback>
            </Avatar>
            {store.is_verified && (
              <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center border-2 border-background">
                <ShieldCheck className="w-3.5 h-3.5 text-white" />
              </div>
            )}
          </div>

          {/* Name & Actions */}
          <div className="flex-1">
            <div className="flex flex-col sm:flex-row sm:items-center gap-3">
              <div>
                <h1 className="text-xl sm:text-2xl font-bold text-foreground flex items-center gap-2">
                  {store.name}
                  {store.is_verified && (
                    <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 text-xs">
                      Verified
                    </Badge>
                  )}
                </h1>
                {store.description && (
                  <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{store.description}</p>
                )}
              </div>
              <Button
                variant={isFollowing ? 'outline' : 'default'}
                className={`rounded-full h-9 px-6 text-sm font-medium ${
                  !isFollowing
                    ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                    : ''
                }`}
                onClick={handleFollow}
                disabled={isTogglingFollow}
              >
                {isTogglingFollow
                  ? '...'
                  : isFollowing
                  ? 'Following'
                  : 'Follow'}
              </Button>
            </div>
          </div>
        </div>

        {/* Store Stats */}
        <div className="flex items-center gap-6 mt-6 px-4 sm:px-6">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <ShoppingBag className="w-4 h-4" />
            <span>
              <strong className="text-foreground">{store.listings_count}</strong> products
            </span>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Users className="w-4 h-4" />
            <span>
              <strong className="text-foreground">{store.followers_count}</strong> followers
            </span>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <MapPin className="w-4 h-4" />
            <span>Joined {formatDate(store.created_at)}</span>
          </div>
        </div>
      </motion.div>

      {/* Store Listings */}
      <section>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-foreground">Store Products</h2>
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline text-sm text-muted-foreground">{totalCount} items</span>
            <div className="flex items-center rounded-full border bg-muted/30 p-1">
              <Button
                type="button"
                variant={browseLayout === 'grid' ? 'default' : 'ghost'}
                size="sm"
                className="h-8 rounded-full px-3"
                onClick={() => setBrowseLayout('grid')}
              >
                <LayoutGrid className="w-4 h-4" />
              </Button>
              <Button
                type="button"
                variant={browseLayout === 'list' ? 'default' : 'ghost'}
                size="sm"
                className="h-8 rounded-full px-3"
                onClick={() => setBrowseLayout('list')}
              >
                <List className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>

        {listings.length === 0 && !isLoading ? (
          <EmptyState
            icon={Package}
            title="No products yet"
            description="This store hasn't listed any products yet."
            actionLabel="Browse Marketplace"
            onAction={() => router.push(routes.home())}
          />
        ) : browseLayout === 'grid' ? (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 md:gap-6">
              {listings.map((listing) => (
                <ProductCard
                  key={listing.id}
                  listing={listing}
                  onSelect={handleProductSelect}
                  density={browseDensity}
                  showCartControls={browseDensity !== 'compact'}
                />
              ))}
            </div>

            {hasMore && (
              <div className="flex justify-center mt-8">
                <Button
                  variant="outline"
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-full px-8"
                >
                  Load More
                </Button>
              </div>
            )}
          </>
        ) : (
          <div className="space-y-2">
            {listings.map((listing) => (
              <button
                key={listing.id}
                type="button"
                className="w-full rounded-xl border bg-card p-3 text-left hover:bg-muted/20"
                onClick={() => handleProductSelect(listing)}
              >
                <div className="flex items-center gap-3">
                  <div className="w-14 h-14 rounded-lg bg-muted overflow-hidden flex-shrink-0 relative">
                    {(listing.images?.[0] as any)?.image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={(listing.images?.[0] as any)?.image}
                        alt={listing.title}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Package className="w-5 h-5 text-muted-foreground/30" />
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground truncate">{listing.title}</p>
                    <p className="text-xs text-muted-foreground truncate">{listing.city || ''}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                      {listing.price ? `TZS ${Number(listing.price).toLocaleString('en-TZ')}` : 'TZS —'}
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
