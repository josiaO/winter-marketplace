'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Heart,
  Trash2,
  Package,
  ShieldCheck,
  ShoppingCart,
  Check,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/smartdalali/empty-state';
import { SkeletonGrid } from '@/components/smartdalali/skeleton-grid';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS } from '@/lib/helpers';
import { toast } from 'sonner';
import { ApiClientError, type WishlistItem } from '@/types/api';
import { cn } from '@/lib/utils';

export function WishlistPage() {
  const router = useRouter();
  const { isAuthenticated, user } = useAuthStore();

  const [items, setItems] = useState<WishlistItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [removingId, setRemovingId] = useState<number | null>(null);
  const [addedToCart, setAddedToCart] = useState<Record<number, boolean>>({});
  const [cartAddingListingId, setCartAddingListingId] = useState<number | null>(
    null,
  );

  const fetchWishlist = useCallback(async () => {
    if (!isAuthenticated) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const res = await api.commerce.wishlist();
      // Backend currently returns a non-paginated structure:
      // { id, items, total_count, favorites: items } OR marketplace favorites { favorites: [...] }
      const anyRes = res as any;
      const list: WishlistItem[] =
        (anyRes?.items as WishlistItem[] | undefined) ||
        (anyRes?.favorites as WishlistItem[] | undefined) ||
        (anyRes?.results as WishlistItem[] | undefined) ||
        [];
      setItems(list);
    } catch {
      toast.error('Failed to load wishlist');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchWishlist();
  }, [fetchWishlist]);

  const handleRemove = async (id: number) => {
    setRemovingId(id);
    try {
      // Prefer toggle semantics: remove by listing_id when present.
      const item = items.find((x) => x.id === id) as any;
      const listingId = item?.listing?.id ?? item?.listing_id ?? item?.listingId;
      if (!listingId) throw new Error('Missing listing id');
      await api.commerce.wishlistToggle({ listing_id: listingId });
      setItems((prev) => prev.filter((x) => x.id !== id));
      toast.success('Removed from wishlist');
    } catch {
      toast.error('Failed to remove item');
    } finally {
      setRemovingId(null);
    }
  };

  const handleAddToCart = async (e: React.MouseEvent, listingId: number) => {
    e.stopPropagation();
    if (cartAddingListingId != null) return;
    setCartAddingListingId(listingId);
    try {
      await api.commerce.cartAddItem({ listing_id: listingId, quantity: 1 });
      setAddedToCart((prev) => ({ ...prev, [listingId]: true }));
      toast.success('Added to cart!');
      setTimeout(() => {
        setAddedToCart((prev) => {
          const next = { ...prev };
          delete next[listingId];
          return next;
        });
      }, 2000);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        if (err.status === 400 || err.status === 409) {
          toast.error(
            err.detail ||
              err.message ||
              'Not enough stock or invalid quantity.',
          );
        } else {
          toast.error(err.detail || err.message || 'Failed to add to cart');
        }
      } else {
        toast.error('Failed to add to cart');
      }
    } finally {
      setCartAddingListingId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-8 w-40 mb-6" />
        <SkeletonGrid />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <EmptyState
          icon={Heart}
          title="Please login to view wishlist"
          description="You need to be logged in to view and manage your saved items."
          actionLabel="Login"
          onAction={() => router.push(routes.login())}
        />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-6">
            My Wishlist
          </h1>
          <EmptyState
            icon={Heart}
            title="Your wishlist is empty"
            description="Save items you love to your wishlist. They'll appear here so you can easily find them later."
            actionLabel="Explore Products"
            onAction={() => router.push(routes.home())}
          />
        </motion.div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
            My Wishlist
          </h1>
          <span className="text-sm text-muted-foreground">
            {items.length} {items.length === 1 ? 'item' : 'items'}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 md:gap-6">
          <AnimatePresence>
            {items.map((wishlistItem, index) => {
              const listing = wishlistItem.listing;
              const primaryImage = listing.images?.find((img) => img.is_primary) || listing.images?.[0];
              const sellerName =
                listing.seller?.first_name && listing.seller?.last_name
                  ? `${listing.seller.first_name} ${listing.seller.last_name}`
                  : listing.seller?.username || '';

              return (
                <motion.div
                  key={wishlistItem.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  transition={{ duration: 0.3, delay: index * 0.04 }}
                  className="group rounded-xl border bg-card overflow-hidden"
                >
                  {/* Image */}
                  <div
                    className="relative aspect-square overflow-hidden bg-muted cursor-pointer"
                    onClick={() => router.push(routes.product(String(listing.id)))}
                  >
                    {primaryImage?.image ? (
                      <Image
                        src={primaryImage.image}
                        alt={listing.title}
                        fill
                        className="object-cover transition-transform duration-500 group-hover:scale-105"
                        sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Package className="w-12 h-12 text-muted-foreground/40" />
                      </div>
                    )}

                    {/* Condition Badge */}
                    <Badge
                      variant="secondary"
                      className={cn(
                        'absolute top-2 left-2 text-xs font-medium capitalize',
                        listing.condition === 'new'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400'
                          : 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400'
                      )}
                    >
                      {listing.condition}
                    </Badge>

                    {/* Remove Button */}
                    <Button
                      variant="secondary"
                      size="icon"
                      className={cn(
                        'absolute top-2 right-2 h-8 w-8 rounded-full bg-background/80 backdrop-blur-sm',
                        'hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/30 dark:hover:text-red-400',
                        'transition-colors opacity-0 group-hover:opacity-100'
                      )}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleRemove(wishlistItem.id);
                      }}
                      disabled={removingId === wishlistItem.id}
                    >
                      {removingId === wishlistItem.id ? (
                        <div className="w-4 h-4 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <Trash2 className="w-4 h-4" />
                      )}
                    </Button>
                  </div>

                  {/* Content */}
                  <div className="p-3 sm:p-4 space-y-2">
                    {/* Title */}
                    <h3
                      className="font-medium text-sm leading-snug line-clamp-2 text-foreground group-hover:text-primary transition-colors cursor-pointer"
                      onClick={() => router.push(routes.product(String(listing.id)))}
                    >
                      {listing.title}
                    </h3>

                    {/* Price */}
                    <div className="flex items-baseline gap-1">
                      <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                        {formatTZS(listing.price)}
                      </span>
                    </div>

                    {/* Seller */}
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs text-muted-foreground truncate">
                        by {sellerName}
                      </span>
                      {listing.seller?.is_verified && (
                        <ShieldCheck className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2 pt-1">
                      <Button
                        size="sm"
                        className={cn(
                          'flex-1 rounded-lg text-xs h-9 transition-all duration-300',
                          addedToCart[listing.id]
                            ? 'bg-emerald-600 hover:bg-emerald-600 text-white'
                            : 'bg-primary hover:bg-primary/90 text-primary-foreground'
                        )}
                        onClick={(e) => handleAddToCart(e, listing.id)}
                        disabled={
                          cartAddingListingId === listing.id ||
                          (typeof listing.stock_quantity === 'number' &&
                            listing.stock_quantity < 1)
                        }
                      >
                        {addedToCart[listing.id] ? (
                          <>
                            <Check className="w-4 h-4 mr-1" />
                            Added
                          </>
                        ) : cartAddingListingId === listing.id ? (
                          <div className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin mx-auto" />
                        ) : (
                          <>
                            <ShoppingCart className="w-4 h-4 mr-1" />
                            Add to Cart
                          </>
                        )}
                      </Button>
                      <Button
                        variant="outline"
                        size="icon"
                        className="h-9 w-9 flex-shrink-0 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg"
                        onClick={() => handleRemove(wishlistItem.id)}
                        disabled={removingId === wishlistItem.id}
                      >
                        {removingId === wishlistItem.id ? (
                          <div className="w-4 h-4 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <Heart className="w-4 h-4 fill-current" />
                        )}
                      </Button>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );
}
