'use client';

import { useState } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { ShoppingCart, Check, ShieldCheck, Package, Heart, Plus, Minus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAuthStore } from '@/store';
import { cn } from '@/lib/utils';
import { formatTZS, truncateText } from '@/lib/helpers';
import { api } from '@/lib/api-client';
import { toast } from 'sonner';
import { ApiClientError, type Listing } from '@/types/api';

interface ProductCardProps {
  listing: Listing;
  onSelect?: (listing: Listing) => void;
  className?: string;
}

export function ProductCard({ listing, onSelect, className }: ProductCardProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [addedToCart, setAddedToCart] = useState(false);
  const [isFavoriting, setIsFavoriting] = useState(false);
  const [isFavorite, setIsFavorite] = useState(listing.is_liked || false);
  const [quantity, setQuantity] = useState(1);
  const { isAuthenticated } = useAuthStore();

  const primaryImage = listing.images?.find((img) => img.is_primary) || listing.images?.[0];

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isAdding) return;
    if (!isAuthenticated) {
      toast.error('Please login to add items to cart');
      return;
    }
    const stock = listing.stock_quantity;
    if (typeof stock === 'number' && stock < 1) {
      toast.error('This item is out of stock');
      return;
    }

    setIsAdding(true);
    try {
      await api.commerce.cartAddItem({ listing_id: listing.id, quantity });
      setAddedToCart(true);
      toast.success(`Added ${quantity} item(s) to cart!`);
      setTimeout(() => setAddedToCart(false), 2000);
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        if (err.status === 400 || err.status === 409) {
          toast.error(
            err.detail ||
              err.message ||
              'Not enough stock or invalid quantity.',
          );
        } else if (err.status === 401) {
          toast.error('Session expired. Please login again.');
        } else {
          toast.error(err.detail || err.message || 'Failed to add to cart');
        }
      } else {
        toast.error('Failed to add to cart due to a network error');
      }
    } finally {
      setIsAdding(false);
    }
  };

  const handleToggleFavorite = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isFavoriting) return;
    if (!isAuthenticated) {
      toast.error('Please login to save favorites');
      return;
    }

    setIsFavoriting(true);
    try {
      const res = await api.listings.toggleLike(listing.id);
      setIsFavorite(res.status === 'liked');
      toast.success(res.status === 'liked' ? 'Saved to favorites' : 'Removed from favorites');
    } catch {
      toast.error('Failed to update favorites');
    } finally {
      setIsFavoriting(false);
    }
  };

  const sellerName =
    listing.seller?.first_name && listing.seller?.last_name
      ? truncateText(`${listing.seller.first_name} ${listing.seller.last_name}`, 18)
      : truncateText(listing.seller?.username || '', 18);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' as const }}
      whileHover={{ y: -4 }}
      className={cn(
        'group rounded-xl border bg-card overflow-hidden cursor-pointer',
        'transition-shadow duration-300 hover:shadow-lg',
        className
      )}
      onClick={() => onSelect?.(listing)}
    >
      {/* Image */}
      <div className="relative aspect-square overflow-hidden bg-muted">
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

        {/* Featured Badge */}
        {listing.is_featured && (
          <Badge className="absolute top-2 right-2 bg-emerald-500 text-white text-xs font-medium">
            Featured
          </Badge>
        )}

        {/* Favorite Button */}
        <button
          onClick={handleToggleFavorite}
          disabled={isFavoriting}
          className={cn(
            'absolute bottom-2 right-2 w-8 h-8 rounded-full flex items-center justify-center shadow-sm transition-all',
            isFavorite
              ? 'bg-red-500 text-white'
              : 'bg-white/80 text-gray-600 hover:bg-white dark:bg-black/60 dark:text-gray-300'
          )}
        >
          <Heart className={cn('w-4 h-4', isFavorite && 'fill-current')} />
        </button>
      </div>

      {/* Content */}
      <div className="p-3 sm:p-4 space-y-2">
        {/* Title */}
        <h3 className="font-medium text-sm leading-snug line-clamp-2 text-foreground group-hover:text-primary transition-colors">
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
          <span className="text-xs text-muted-foreground">
            by {sellerName}
          </span>
          {listing.seller?.is_verified && (
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />
          )}
        </div>

        {/* Location */}
        {listing.city && (
          <span className="text-xs text-muted-foreground">{listing.city}</span>
        )}

        {/* Quantity and Add to Cart */}
        <div className="flex items-center gap-2 mt-2">
          <div className="flex items-center border rounded-lg bg-muted/30">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setQuantity(Math.max(1, quantity - 1));
              }}
              className="px-2 py-1 hover:bg-muted rounded-l-lg transition-colors"
              disabled={quantity <= 1 || isAdding}
            >
              <Minus className="w-3 h-3" />
            </button>
            <span className="w-6 text-center text-xs font-medium">{quantity}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setQuantity(Math.min(listing.stock_quantity || 99, quantity + 1));
              }}
              className="px-2 py-1 hover:bg-muted rounded-r-lg transition-colors"
              disabled={quantity >= (listing.stock_quantity || 99) || isAdding}
            >
              <Plus className="w-3 h-3" />
            </button>
          </div>

          <Button
            size="sm"
            className={cn(
              'flex-1 rounded-lg text-xs h-9 transition-all duration-300',
              addedToCart
                ? 'bg-emerald-600 hover:bg-emerald-600 text-white'
                : 'bg-primary hover:bg-primary/90 text-primary-foreground'
            )}
            onClick={handleAddToCart}
            disabled={
              isAdding ||
              (typeof listing.stock_quantity === 'number' &&
                listing.stock_quantity < 1)
            }
          >
            {addedToCart ? (
              <>
                <Check className="w-4 h-4 mr-1" />
                Added
              </>
            ) : isAdding ? (
              <div className="w-4 h-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <ShoppingCart className="w-4 h-4 mr-1" />
                Add
              </>
            )}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
