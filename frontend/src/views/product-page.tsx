'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
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
  AlertTriangle,
  ArrowRight,
  MessageSquare,
  Flag,
  XCircle,
  Loader2,
  CheckCircle2,
} from 'lucide-react';
import { AnimatePresence } from 'framer-motion';
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
import { Textarea } from '@/components/ui/textarea';
import { useAuthStore, useCartStore } from '@/store';
import { fetchCartForStore } from '@/lib/django-cart-adapter';
import { api } from '@/lib/api-client';
import { formatTZS, getInitials, getRelativeTime, formatDate } from '@/lib/helpers';
import { toast } from 'sonner';
import {
  ApiClientError,
  type Listing,
  type ListingAttributeValueRow,
  type Review,
  type Order,
  type PaginatedResponse,
  type ReportReason,
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

export function ProductPage({ productId }: { productId: string }) {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: isAuthLoading } = useAuthStore();
  const { setCart } = useCartStore();
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
  const [showReportDialog, setShowReportDialog] = useState(false);
  const [reportReason, setReportReason] = useState<ReportReason>('spam');
  const [reportDescription, setReportDescription] = useState('');
  const [isReporting, setIsReporting] = useState(false);

  // Review System State
  const [canReview, setCanReview] = useState(false);
  const [reviewOrder, setReviewOrder] = useState<Order | null>(null);
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewComment, setReviewComment] = useState('');
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  const fetchReviews = useCallback(async () => {
    if (!productId) return;
    setIsLoadingReviews(true);
    try {
      const data = await api.trust.reviews({ listing: productId });
      setReviews(data.results);
    } catch {
      console.error('Failed to load reviews');
    } finally {
      setIsLoadingReviews(false);
    }
  }, [productId]);

  // Parallelize core data fetching
  useEffect(() => {
    if (!productId) return;
    setIsLoading(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });

    const loadData = async () => {
      try {
        // Core data can always be fetched
        const [listingData, reviewsData] = await Promise.all([
          api.listings.detail(productId),
          api.trust.reviews({ listing: productId }),
        ]);

        setListing(listingData);
        setReviews(reviewsData.results);
        setIsLoadingReviews(false);

        // Set primary image
        const primaryIdx = listingData.images?.findIndex((img) => img.is_primary);
        if (primaryIdx >= 0) setSelectedImage(primaryIdx);

        // Optional eligibility check (don't block main UI for this)
        // Optional eligibility check (don't block main UI for this)
        if (!isAuthLoading && isAuthenticated && user) {
          api.commerce.orders({ status: 'delivered', role: 'buyer' })
            .then((res) => {
              const eligibleOrder = res.results.find((o: Order) =>
                o.items.some((item) => {
                  const itemId = item.listing_id || (item.listing as any)?.id;
                  return String(itemId) === String(productId);
                }),
              );
              if (eligibleOrder) {
                setCanReview(true);
                setReviewOrder(eligibleOrder);
              }
            })
            .catch((err) => console.error('Eligibility check failed', err));
        }
      } catch (err) {
        toast.error('Failed to load product');
        router.push(routes.home());
      } finally {
        setIsLoading(false);
      }
    };

    void loadData();
  }, [productId, router, isAuthenticated, user, isAuthLoading]);

  const handleSubmitReview = async () => {
    if (!reviewOrder) return;
    setIsSubmittingReview(true);
    try {
      await api.commerce.reviewOrder(reviewOrder.id, {
        rating: reviewRating,
        comment: reviewComment,
      });
      toast.success('Review submitted successfully!');
      setCanReview(false);
      fetchReviews();
    } catch (err) {
      toast.error('Failed to submit review');
    } finally {
      setIsSubmittingReview(false);
    }
  };

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
    if (isAddingToCart) return;
    if (!isAuthenticated) {
      toast.error('Please login to add items to cart');
      return;
    }
    const stock = listing?.stock_quantity;
    if (typeof stock === 'number' && stock < 1) {
      toast.error('This item is out of stock');
      return;
    }
    setIsAddingToCart(true);
    try {
      await api.commerce.cartAddItem({
        listing_id: Number(productId),
        quantity: 1,
      });
      await fetchCartForStore(setCart);
      toast.success('Added to cart!');
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
      setIsAddingToCart(false);
    }
  }, [isAddingToCart, isAuthenticated, productId, listing?.stock_quantity, setCart]);

  const handleBuyNow = useCallback(async () => {
    if (isAddingToCart) return;
    if (!isAuthenticated) {
      toast.error('Please login to purchase');
      return;
    }
    const stock = listing?.stock_quantity;
    if (typeof stock === 'number' && stock < 1) {
      toast.error('This item is out of stock');
      return;
    }
    setIsAddingToCart(true);
    try {
      await api.commerce.cartAddItem({
        listing_id: Number(productId),
        quantity: 1,
      });
      await fetchCartForStore(setCart);
      router.push(routes.cart());
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        toast.error(
          err.detail ||
            err.message ||
            'Could not add to cart. Check stock and try again.',
        );
      } else {
        toast.error('Failed to proceed. Please try adding to cart first.');
      }
    } finally {
      setIsAddingToCart(false);
    }
  }, [
    isAddingToCart,
    isAuthenticated,
    productId,
    listing?.stock_quantity,
    router,
    setCart,
  ]);

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

  const handleReportListing = useCallback(async () => {
    if (!isAuthenticated) {
      toast.error('Please login to report this listing');
      return;
    }
    if (!reportDescription.trim()) {
      toast.error('Please provide a description for the report');
      return;
    }
    setIsReporting(true);
    try {
      await api.trust.createReport({
        listing: Number(productId),
        reason: reportReason,
        description: reportDescription.trim(),
      });
      toast.success('Listing reported. Our moderators will review it.');
      setShowReportDialog(false);
      setReportDescription('');
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError ? err.detail || err.message : 'Failed to submit report';
      toast.error(msg);
    } finally {
      setIsReporting(false);
    }
  }, [isAuthenticated, productId, reportReason, reportDescription]);

  const handleProductSelect = useCallback(
    (l: Listing) => router.push(routes.product(String(l.id))),
    [router]
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

  // Backend may return seller info under different keys, and may be an ID or an object.
  const sellerData: any = (listing as any).seller ?? (listing as any).owner ?? null;
  const sellerUser = typeof sellerData === 'object' ? sellerData : null;
  const sellerId = typeof sellerData === 'object' ? sellerData?.id : sellerData;

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
              onClick={() => router.push(routes.home())}
            >
              <Home className="w-4 h-4" />
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink
              className="cursor-pointer text-sm"
              onClick={() => router.push(routes.category(listing.category.slug))}
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
            <AnimatePresence mode="wait">
              <motion.div
                key={selectedImage}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="absolute inset-0"
              >
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
              </motion.div>
            </AnimatePresence>

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
                  onClick={() => router.push(routes.store(storeSlug))}
                >
                  <Store className="w-3.5 h-3.5 mr-1" />
                  Store
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                className="text-xs h-8 rounded-lg"
                onClick={async () => {
                  if (isAuthLoading) return;
                  if (!isAuthenticated) {
                    toast.error('Please login to message the seller');
                    return;
                  }
                  const targetSellerId = sellerId;
                  if (!targetSellerId) return;
                  try {
                    const conv = await api.communications.startConversation({
                      seller_id: targetSellerId,
                      listing_id: Number(productId),
                    });
                    router.push(routes.messageThread(String(conv.id)));
                  } catch (err) {
                    toast.error('Failed to start conversation');
                  }
                }}
                disabled={!sellerId}
              >
                <MessageSquare className="w-3.5 h-3.5 mr-1" />
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
              disabled={
                isAddingToCart ||
                (typeof listing.stock_quantity === 'number' &&
                  listing.stock_quantity < 1)
              }
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
              disabled={
                isAddingToCart ||
                (typeof listing.stock_quantity === 'number' &&
                  listing.stock_quantity < 1)
              }
            >
              <Zap className="w-5 h-5 mr-2" />
              Buy Now
            </Button>
          </div>

          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              className="text-xs text-muted-foreground hover:text-red-600 gap-1.5 h-8 px-2"
              onClick={() => setShowReportDialog(true)}
            >
              <Flag className="w-3.5 h-3.5" />
              Report listing
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

            {/* Rating Summary Logic moved, Form moved to main list top */}
          </div>

          {/* Reviews List */}
          <div className="lg:col-span-2 space-y-6">
            {canReview && (
              <motion.div
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                className="p-6 rounded-2xl border-2 border-emerald-500/20 bg-emerald-50/30 dark:bg-emerald-900/10 shadow-sm"
              >
                <div className="flex items-center gap-2 mb-4">
                  <Star className="w-5 h-5 text-emerald-600 fill-emerald-600" />
                  <h4 className="text-lg font-bold text-foreground">
                    Share your experience
                  </h4>
                </div>
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <button
                        key={i}
                        onClick={() => setReviewRating(i + 1)}
                        className="focus:outline-none transition-all hover:scale-110"
                      >
                        <Star
                          className={`w-7 h-7 ${
                            i < reviewRating
                              ? 'fill-amber-400 text-amber-400'
                              : 'text-gray-300 dark:text-gray-600'
                          }`}
                        />
                      </button>
                    ))}
                  </div>
                  <Textarea
                    placeholder="Tell others what you think about this product..."
                    value={reviewComment}
                    onChange={(e) => setReviewComment(e.target.value)}
                    className="text-base rounded-xl min-h-[100px] bg-background"
                  />
                  <div className="flex justify-end">
                    <Button
                      size="lg"
                      className="px-8 rounded-xl bg-emerald-600 hover:bg-emerald-700 font-semibold"
                      onClick={handleSubmitReview}
                      disabled={isSubmittingReview}
                    >
                      {isSubmittingReview ? (
                        <Loader2 className="w-5 h-5 animate-spin mr-2" />
                      ) : (
                        <CheckCircle2 className="w-5 h-5 mr-2" />
                      )}
                      Submit Review
                    </Button>
                  </div>
                </div>
              </motion.div>
            )}

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
      {/* Report Dialog (Simple Modal Implementation) */}
      <AnimatePresence>
        {showReportDialog && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="bg-background border rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
            >
              <div className="p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-red-600">
                    <AlertTriangle className="w-5 h-5" />
                    <h3 className="text-lg font-bold">Report Listing</h3>
                  </div>
                  <Button variant="ghost" size="icon" onClick={() => setShowReportDialog(false)} className="h-8 w-8">
                    <XCircle className="w-5 h-5" />
                  </Button>
                </div>

                <div className="space-y-3">
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Reason for reporting</label>
                    <select
                      className="w-full h-10 rounded-md border bg-background px-3 text-sm"
                      value={reportReason}
                      onChange={(e) => setReportReason(e.target.value as ReportReason)}
                    >
                      <option value="spam">Spam or misleading</option>
                      <option value="fraud">Fraud or scam</option>
                      <option value="inappropriate">Inappropriate content</option>
                      <option value="duplicate">Duplicate listing</option>
                      <option value="wrong_category">Wrong category</option>
                      <option value="other">Other issue</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="text-sm font-medium">Description</label>
                    <textarea
                      className="w-full min-h-[100px] rounded-md border bg-background p-3 text-sm resize-none"
                      placeholder="Please provide details about what is wrong with this listing..."
                      value={reportDescription}
                      onChange={(e) => setReportDescription(e.target.value)}
                    />
                  </div>
                </div>

                <div className="flex gap-3 pt-2">
                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={() => setShowReportDialog(false)}
                    disabled={isReporting}
                  >
                    Cancel
                  </Button>
                  <Button
                    className="flex-1 bg-red-600 hover:bg-red-700"
                    onClick={handleReportListing}
                    disabled={isReporting}
                  >
                    {isReporting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Flag className="w-4 h-4 mr-2" />}
                    Submit Report
                  </Button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
