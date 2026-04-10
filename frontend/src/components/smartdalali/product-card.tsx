'use client';

import { useState } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { ShoppingCart, Check, ShieldCheck, Package } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useAuthStore } from '@/store';
import { cn } from '@/lib/utils';
import { formatTZS, truncateText } from '@/lib/helpers';
import { api } from '@/lib/api-client';
import { toast } from 'sonner';
import type { Listing } from '@/types/api';

interface ProductCardProps {
  listing: Listing;
  onSelect?: (listing: Listing) => void;
  className?: string;
}

export function ProductCard({ listing, onSelect, className }: ProductCardProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [addedToCart, setAddedToCart] = useState(false);
  const { isAuthenticated } = useAuthStore();

  const primaryImage = listing.images?.find((img) => img.is_primary) || listing.images?.[0];

  const handleAddToCart = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isAuthenticated) {
      toast.error('Please login to add items to cart');
      return;
    }

    setIsAdding(true);
    try {
      await api.commerce.cartAddItem({ listing_id: listing.id });
      setAddedToCart(true);
      toast.success('Added to cart!');
      setTimeout(() => setAddedToCart(false), 2000);
    } catch {
      toast.error('Failed to add to cart');
    } finally {
      setIsAdding(false);
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

        {/* Add to Cart */}
        <Button
          size="sm"
          className={cn(
            'w-full mt-1 rounded-lg text-xs h-9 transition-all duration-300',
            addedToCart
              ? 'bg-emerald-600 hover:bg-emerald-600 text-white'
              : 'bg-primary hover:bg-primary/90 text-primary-foreground'
          )}
          onClick={handleAddToCart}
          disabled={isAdding}
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
              Add to Cart
            </>
          )}
        </Button>
      </div>
    </motion.div>
  );
}
