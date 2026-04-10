'use client';

import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import {
  ShoppingCart,
  Zap,
  ShieldCheck,
  Package,
  Star,
  Home,
  Heart,
  MessageCircle,
  Store,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
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
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, getInitials, getRelativeTime, formatDate } from '@/lib/helpers';
import { toast } from 'sonner';
import type {
  Listing,
  ListingAttributeValueRow,
  Review,
  PaginatedResponse,
} from '@/types/api';

function collectSpecificationRows(listing: Listing): Array<{ label: string; value: string }> {
  const rows: Array<{ label: string; value: string }> = [];
  const seen = new Set<string>();

  const push = (label: string, value: unknown) => {
    if (value === null || value === undefined || value === '') return;
    const v =
      typeof value === 'object' ? JSON.stringify(value) : String(value);
    const key = `${label}:${v}`;
    if (seen.has(key)) return;
    seen.add(key);
    rows.push({ label, value: v });
  };

  const specs = listing.specs;
  if (specs && typeof specs === 'object' && !Array.isArray(specs)) {
    for (const [k, v] of Object.entries(specs as Record<string, unknown>)) {
      push(k.replace(/_/g, ' '), v);
    }
  }

  const legacy = listing.attributes;
  if (legacy && typeof legacy === 'object' && !Array.isArray(legacy)) {
    for (const [k, v] of Object.entries(legacy)) {
      push(k.replace(/_/g, ' '), v);
    }
  }

  for (const av of listing.attribute_values ?? []) {
    const label =
      (av as ListingAttributeValueRow).label ||
      (av as ListingAttributeValueRow).name ||
      (av as ListingAttributeValueRow).key;
    push(label, (av as ListingAttributeValueRow).value);
  }

  return rows;
}

export function ProductPage() {
  const { currentView, navigate } = useUIStore();
  const { isAuthenticated } = useAuthStore();

  const productId = currentView.view === 'product' ? currentView.id : '';
  const [listing, setListing] = useState<Listing | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(0);
  const [isAddingToCart, setIsAddingToCart] = useState(false);
  const [isLiked, setIsLiked] = useState(false);
  const [isTogglingLike, setIsTogglingLike] = useState(false);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [isLoadingReviews, setIsLoadingReviews] = useState(true);
  const [relatedProducts, setRelatedProducts] = useState<Listing[]>([]);
  const [isLoadingRelated, setIsLoadingRelated] = useState(false);

  // Fetch listing detail
  useEffect(() => {
    if (!productId) return;
    setIsLoading(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });

    api.listings
      .detail(productId)
      .then((data) => {
        setListing(data);
        // Set initial image to primary
        const primaryIdx = data.images?.findIndex((img) => img.is_primary);
        if (primaryIdx >= 0) setSelectedImage(primaryIdx);
      })
      .catch(() => {
        toast.error('Failed to load product');
        navigate({ view: 'home' });
      })
      .finally(() => setIsLoading(false));
  }, [productId, navigate]);

  // Fetch reviews
  useEffect(() => {
    if (!productId) return;
    setIsLoadingReviews(true);
    api.trust
      .reviews({ listing: productId })
      .then((res) => {
        setReviews(res.results || []);
      })
      .catch(() => setReviews([]))
      .finally(() => setIsLoadingReviews(false));
  }, [productId]);

  // Fetch related products (same category)
  useEffect(() => {
    if (!listing?.category?.id) return;
    setIsLoadingRelated(true);
    api.listings
      .list({ category: listing.category.id })
      .then((res) => {
        setRelatedProducts((res.results || []).filter((p) => p.id !== listing.id).slice(0, 4));
      })
      .catch(() => setRelatedProducts([]))
      .finally(() => setIsLoadingRelated(false));
  }, [listing?.category?.id, listing?.id]);

  const handleAddToCart = useCallback(async () => {
    if (!isAuthenticated) {
      toast.error('Please login to add items to cart');
      return;
    }
    setIsAddingToCart(true);
    try {
      await api.commerce.cartAddItem({ listing_id: Number(productId) });
      toast.success('Added to cart!');
    } catch {
      toast.error('Failed to add to cart');
    } finally {
      setIsAddingToCart(false);
    }
  }, [isAuthenticated, productId]);

  const handleBuyNow = useCallback(async () => {
    if (!isAuthenticated) {
      toast.error('Please login to purchase');
      return;
    }
    try {
      await api.commerce.cartAddItem({ listing_id: Number(productId) });
      navigate({ view: 'cart' });
    } catch {
      toast.error('Failed to proceed. Please try adding to cart first.');
    }
  }, [isAuthenticated, productId, navigate]);

  const handleToggleLike = useCallback(async () => {
    if (!isAuthenticated) {
      toast.error('Please login to add to wishlist');
      return;
    }
    setIsTogglingLike(true);
    try {
      const res = await api.commerce.wishlistToggle({
        listing_id: Number(productId),
      });
      setIsLiked(Boolean(res.added));
      toast.success(
        res.added ? 'Added to wishlist!' : 'Removed from wishlist',
      );
    } catch {
      toast.error('Failed to update wishlist');
    } finally {
      setIsTogglingLike(false);
    }
  }, [isAuthenticated, productId]);

  const handleProductSelect = useCallback(
    (l: Listing) => navigate({ view: 'product', id: String(l.id) }),
    [navigate]
  );

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-4 w-48 mb-6" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <Skeleton className="aspect-square rounded-2xl" />
          <div className="space-y-4">
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-6 w-1/3" />
            <Skeleton className="h-4 w-1/2" />
            <Separator />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        </div>
      </div>
    );
  }

  if (!listing) return null;

  const specRows = collectSpecificationRows(listing);
  const images = listing.images || [];
  const primaryImage = images[selectedImage] || images[0];

  // Rating summary
  const ratingDist: Record<number, number> = { 5: 0, 4: 0, 3: 0, 2: 0, 1: 0 };
  reviews.forEach((r) => {
    if (r.rating >= 1 && r.rating <= 5) ratingDist[r.rating]++;
  });
  const avgRating =
    reviews.length > 0
      ? reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length
      : 0;

  // Backend may return seller info under different keys, and may be missing for some listings.
  const sellerUser: any = (listing as any).seller ?? (listing as any).owner ?? null;

  const sellerFullName =
    sellerUser?.first_name && sellerUser?.last_name
      ? `${sellerUser.first_name} ${sellerUser.last_name}`
      : sellerUser?.username || 'Seller';

  const storeSlug = sellerUser?.seller_profile?.store?.slug;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Breadcrumb */}
      <Breadcrumb className="mb-6">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink
              className="cursor-pointer text-sm"
              onClick={() => navigate({ view: 'home' })}
            >
              <Home className="w-4 h-4" />
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink
              className="cursor-pointer text-sm"
              onClick={() => navigate({ view: 'category', slug: listing.category.slug })}
            >
              {listing.category.name}
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage className="text-sm font-medium max-w-[200px] truncate">
              {listing.title}
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12">
        {/* Image Gallery */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
          className="space-y-3"
        >
          {/* Main Image */}
          <div className="relative aspect-square rounded-2xl overflow-hidden bg-muted border">
            {primaryImage?.image ? (
              <Image
                src={primaryImage.image}
                alt={listing.title}
                fill
                className="object-cover"
                sizes="(max-width: 1024px) 100vw, 50vw"
                priority
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <Package className="w-16 h-16 text-muted-foreground/30" />
              </div>
            )}

            {/* Navigation arrows */}
            {images.length > 1 && (
              <>
                <button
                  onClick={() => setSelectedImage((i) => (i === 0 ? images.length - 1 : i - 1))}
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/80 dark:bg-black/50 flex items-center justify-center hover:bg-white dark:hover:bg-black/70 transition-colors shadow"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  onClick={() => setSelectedImage((i) => (i === images.length - 1 ? 0 : i + 1))}
                  className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/80 dark:bg-black/50 flex items-center justify-center hover:bg-white dark:hover:bg-black/70 transition-colors shadow"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </>
            )}
          </div>

          {/* Thumbnails */}
          {images.length > 1 && (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {images.map((img, i) => (
                <button
                  key={img.id}
                  onClick={() => setSelectedImage(i)}
                  className={`flex-shrink-0 w-16 h-16 sm:w-20 sm:h-20 rounded-lg overflow-hidden border-2 transition-all ${
                    i === selectedImage
                      ? 'border-emerald-500 ring-2 ring-emerald-500/20'
                      : 'border-transparent hover:border-muted-foreground/30'
                  }`}
                >
                  <Image
                    src={img.image}
                    alt={`${listing.title} ${i + 1}`}
                    width={80}
                    height={80}
                    className="object-cover w-full h-full"
                  />
                </button>
              ))}
            </div>
          )}
        </motion.div>

        {/* Product Info */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="space-y-5"
        >
          {/* Badges */}
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              variant="secondary"
              className={`capitalize ${
                listing.condition === 'new'
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400'
                  : 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400'
              }`}
            >
              {listing.condition}
            </Badge>
            {listing.is_verified && (
              <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400">
                <ShieldCheck className="w-3.5 h-3.5 mr-1" />
                Verified
              </Badge>
            )}
            <Badge variant="outline" className="text-xs">
              {listing.category.name}
            </Badge>
          </div>

          {/* Title */}
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground leading-tight">
            {listing.title}
          </h1>

          {/* Price + delivery */}
          <div className="space-y-1">
            <div className="flex items-baseline gap-2">
              <span className="text-2xl sm:text-3xl font-bold text-emerald-600 dark:text-emerald-400">
                {formatTZS(listing.price)}
              </span>
            </div>
            {listing.delivery_is_free === false &&
            listing.delivery_fee != null &&
            Number(listing.delivery_fee) > 0 ? (
              <p className="text-sm text-muted-foreground">
                Delivery{' '}
                <span className="font-medium text-foreground">
                  {formatTZS(Number(listing.delivery_fee))}
                </span>{' '}
                per unit (summed × quantity at checkout for this seller)
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">Free delivery</p>
            )}
          </div>

          {/* Rating */}
          {reviews.length > 0 && (
            <div className="flex items-center gap-2">
              <div className="flex items-center">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Star
                    key={i}
                    className={`w-4 h-4 ${
                      i < Math.round(avgRating)
                        ? 'fill-amber-400 text-amber-400'
                        : 'text-gray-300 dark:text-gray-600'
                    }`}
                  />
                ))}
              </div>
              <span className="text-sm text-muted-foreground">
                {avgRating.toFixed(1)} ({reviews.length} {reviews.length === 1 ? 'review' : 'reviews'})
              </span>
            </div>
          )}

          <Separator />

          {/* Seller Info Card */}
          <div className="flex items-center gap-3 p-3 rounded-xl bg-muted/50 border">
            <Avatar className="h-10 w-10">
              <AvatarImage src={sellerUser?.avatar || undefined} alt={sellerFullName} />
              <AvatarFallback className="text-xs font-semibold bg-emerald-100 text-emerald-700">
                {getInitials(sellerFullName)}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-sm font-medium text-foreground truncate">
                  {sellerFullName}
                </span>
                {Boolean(sellerUser?.is_verified) && (
                  <ShieldCheck className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                )}
              </div>
              <span className="text-xs text-muted-foreground">
                {sellerUser?.seller_profile?.business_name || 'Seller'}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {storeSlug && (
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs h-8 rounded-lg"
                  onClick={() => navigate({ view: 'store', slug: storeSlug })}
                >
                  <Store className="w-3.5 h-3.5 mr-1" />
                  Store
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                className="text-xs h-8 rounded-lg"
                onClick={() => {
                  const sellerId = sellerUser?.id;
                  if (sellerId) navigate({ view: 'seller-profile', id: String(sellerId) });
                }}
                disabled={!sellerUser?.id}
              >
                <MessageCircle className="w-3.5 h-3.5 mr-1" />
                Message
              </Button>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-3">
            <Button
              size="lg"
              className="flex-1 rounded-xl h-12 text-base font-semibold"
              onClick={handleAddToCart}
              disabled={isAddingToCart}
            >
              {isAddingToCart ? (
                <div className="w-5 h-5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <ShoppingCart className="w-5 h-5 mr-2" />
                  Add to Cart
                </>
              )}
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="h-12 w-12 rounded-xl p-0"
              onClick={handleToggleLike}
              disabled={isTogglingLike}
            >
              <Heart
                className={`w-5 h-5 transition-colors ${
                  isLiked ? 'fill-red-500 text-red-500' : 'text-muted-foreground'
                }`}
              />
            </Button>
            <Button
              size="lg"
              className="flex-1 rounded-xl h-12 text-base font-semibold bg-emerald-600 hover:bg-emerald-700"
              onClick={handleBuyNow}
            >
              <Zap className="w-5 h-5 mr-2" />
              Buy Now
            </Button>
          </div>

          {/* Description */}
          <div>
            <h3 className="text-base font-semibold text-foreground mb-2">Description</h3>
            <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-line">
              {listing.description}
            </p>
          </div>

          {/* Specifications: specs JSON + marketplace attribute_values */}
          {specRows.length > 0 && (
            <div>
              <h3 className="text-base font-semibold text-foreground mb-2">
                Specifications
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {specRows.map((row, idx) => (
                  <div
                    key={`${row.label}-${idx}`}
                    className="p-2 rounded-lg bg-muted/50 text-sm"
                  >
                    <span className="text-muted-foreground capitalize">
                      {row.label}
                    </span>
                    <p className="font-medium text-foreground break-words">
                      {row.value}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Location */}
          {(listing.city || listing.location) && (
            <div className="text-sm text-muted-foreground">
              📍 {listing.city}{listing.location ? `, ${listing.location}` : ''}
            </div>
          )}
        </motion.div>
      </div>

      {/* Reviews Section */}
      <section className="mt-12">
        <Separator className="mb-8" />
        <h2 className="text-xl sm:text-2xl font-bold text-foreground mb-6">Customer Reviews</h2>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Rating Summary */}
          <div className="p-5 rounded-xl border bg-card">
            <div className="text-center mb-4">
              <div className="text-4xl font-bold text-foreground">
                {avgRating > 0 ? avgRating.toFixed(1) : '—'}
              </div>
              <div className="flex items-center justify-center mt-1">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Star
                    key={i}
                    className={`w-5 h-5 ${
                      i < Math.round(avgRating)
                        ? 'fill-amber-400 text-amber-400'
                        : 'text-gray-300 dark:text-gray-600'
                    }`}
                  />
                ))}
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                {reviews.length} {reviews.length === 1 ? 'review' : 'reviews'}
              </p>
            </div>
            <div className="space-y-2">
              {[5, 4, 3, 2, 1].map((star) => (
                <div key={star} className="flex items-center gap-2">
                  <span className="text-xs w-3 text-right">{star}</span>
                  <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                  <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-400 rounded-full transition-all"
                      style={{
                        width:
                          reviews.length > 0
                            ? `${(ratingDist[star] / reviews.length) * 100}%`
                            : '0%',
                      }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground w-6 text-right">
                    {ratingDist[star]}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Reviews List */}
          <div className="lg:col-span-2 space-y-4">
            {isLoadingReviews ? (
              <div className="space-y-4">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="p-4 rounded-xl border space-y-2">
                    <div className="flex items-center gap-2">
                      <Skeleton className="h-8 w-8 rounded-full" />
                      <Skeleton className="h-4 w-24" />
                    </div>
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-3 w-3/4" />
                  </div>
                ))}
              </div>
            ) : reviews.length === 0 ? (
              <div className="text-center py-8">
                <Star className="w-10 h-10 text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No reviews yet. Be the first to review!</p>
              </div>
            ) : (
              <div className="space-y-4 max-h-96 overflow-y-auto pr-1">
                {reviews.map((review) => {
                  const reviewerName =
                    review.reviewer.first_name && review.reviewer.last_name
                      ? `${review.reviewer.first_name} ${review.reviewer.last_name}`
                      : review.reviewer.username;

                  return (
                    <motion.div
                      key={review.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="p-4 rounded-xl border bg-card"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Avatar className="h-7 w-7">
                            <AvatarImage src={review.reviewer.avatar || undefined} alt={reviewerName} />
                            <AvatarFallback className="text-[10px]">
                              {getInitials(reviewerName)}
                            </AvatarFallback>
                          </Avatar>
                          <span className="text-sm font-medium">{reviewerName}</span>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {getRelativeTime(review.created_at)}
                        </span>
                      </div>
                      <div className="flex items-center mb-1">
                        {Array.from({ length: 5 }).map((_, i) => (
                          <Star
                            key={i}
                            className={`w-3 h-3 ${
                              i < review.rating
                                ? 'fill-amber-400 text-amber-400'
                                : 'text-gray-300 dark:text-gray-600'
                            }`}
                          />
                        ))}
                      </div>
                      {review.comment && (
                        <p className="text-sm text-muted-foreground">{review.comment}</p>
                      )}
                      {review.seller_reply && (
                        <div className="mt-2 ml-4 p-2 rounded-lg bg-muted/50 border-l-2 border-emerald-500">
                          <p className="text-xs font-medium text-emerald-700 dark:text-emerald-400 mb-0.5">
                            Seller Reply
                          </p>
                          <p className="text-sm text-muted-foreground">{review.seller_reply}</p>
                        </div>
                      )}
                    </motion.div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Related Products */}
      {relatedProducts.length > 0 && (
        <section className="mt-12">
          <Separator className="mb-8" />
          <h2 className="text-xl sm:text-2xl font-bold text-foreground mb-6">Related Products</h2>
          {isLoadingRelated ? (
            <SkeletonGrid />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
              {relatedProducts.map((product) => (
                <ProductCard key={product.id} listing={product} onSelect={handleProductSelect} />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
