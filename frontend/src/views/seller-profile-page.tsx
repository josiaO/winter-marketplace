'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Home,
  Package,
  ShieldCheck,
  Star,
  Calendar,
  MapPin,
  Flag,
  MessageSquare,
  Loader2,
  CheckCircle2,
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
import { api } from '@/lib/api-client';
import { getInitials, formatDate } from '@/lib/helpers';
import { toast } from 'sonner';
import type { Listing, User } from '@/types/api';

export function SellerProfilePage({ sellerId }: { sellerId: string }) {
  const router = useRouter();

  const [seller, setSeller] = useState<User | null>(null);
  const [listings, setListings] = useState<Listing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [totalCount, setTotalCount] = useState(0);
  const [showReportDialog, setShowReportDialog] = useState(false);
  const [isReporting, setIsReporting] = useState(false);
  const [reportReason, setReportReason] = useState('other');
  const [reportText, setReportText] = useState('');

  // Fetch seller detail
  useEffect(() => {
    if (!sellerId) return;
    window.scrollTo({ top: 0, behavior: 'smooth' });

    let cancelled = false;

    const load = async () => {
      setIsLoading(true);
      try {
        const data = await api.marketplace.sellerDetail(sellerId);
        if (!cancelled) setSeller(data);
      } catch {
        if (!cancelled) toast.error('Failed to load seller profile');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    load();

    return () => { cancelled = true; };
  }, [sellerId]);

  // Fetch seller listings
  useEffect(() => {
    if (!sellerId) return;
    api.listings
      .list({ seller: sellerId, page })
      .then((res) => {
        const items = res.results || [];
        setListings((prev) => (page === 1 ? items : [...prev, ...items]));
        setTotalCount(res.count || 0);
        setHasMore(!!res.next);
      })
      .catch(() => setListings([]));
  }, [sellerId, page]);

  const handleProductSelect = useCallback(
    (listing: Listing) => router.push(routes.product(String(listing.id))),
    [router]
  );

  const handleMessageSeller = async () => {
    if (!sellerId) return;
    try {
      const conv = await api.communications.startConversation({ seller_id: sellerId });
      router.push(routes.conversation(String(conv.id)));
    } catch {
      toast.error('Failed to start conversation');
    }
  };

  const submitReport = async () => {
    if (!sellerId) return;
    setIsReporting(true);
    try {
      await api.trust.createReport({
        reported_user: parseInt(sellerId),
        report_type: 'user',
        reason: reportReason as any,
        description: reportText,
      });
      toast.success('Report submitted');
      setShowReportDialog(false);
    } catch {
      toast.error('Failed to submit report');
    } finally {
      setIsReporting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-4 w-48 mb-6" />
        <div className="flex items-center gap-6 mb-8 p-6 rounded-2xl border">
          <Skeleton className="h-20 w-20 rounded-full" />
          <div className="space-y-2 flex-1">
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-64" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
        <SkeletonGrid />
      </div>
    );
  }

  if (!seller) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <EmptyState
          icon={Store}
          title="Seller not found"
          description="The seller profile you're looking for doesn't exist."
          actionLabel="Go Home"
          onAction={() => router.push(routes.home())}
        />
      </div>
    );
  }

  const fullName =
    seller.first_name && seller.last_name
      ? `${seller.first_name} ${seller.last_name}`
      : seller.username;

  const storeSlug = seller.seller_profile?.store?.slug;
  const businessName = seller.seller_profile?.business_name;
  const verificationStatus = seller.seller_profile?.verification_status;
  const isVerifiedSeller = seller.seller_profile?.is_verified || seller.is_verified;

  const storeSlugForLink = storeSlug;

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
            <BreadcrumbPage className="text-sm font-medium">Seller Profile</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      {/* Seller Info Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <div className="p-6 rounded-2xl border bg-card">
          <div className="flex flex-col sm:flex-row items-start gap-6">
            {/* Avatar */}
            <div className="relative flex-shrink-0">
              <Avatar className="h-20 w-20 sm:h-24 sm:w-24 border-2 border-muted">
                <AvatarImage src={seller.avatar || undefined} alt={fullName} />
                <AvatarFallback className="text-xl font-bold bg-emerald-100 text-emerald-700">
                  {getInitials(fullName)}
                </AvatarFallback>
              </Avatar>
              {isVerifiedSeller && (
                <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center border-2 border-card">
                  <ShieldCheck className="w-3.5 h-3.5 text-white" />
                </div>
              )}
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                <div>
                  <h1 className="text-xl sm:text-2xl font-bold text-foreground flex items-center gap-2 flex-wrap">
                    {fullName}
                    {isVerifiedSeller && (
                      <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 text-xs">
                        <ShieldCheck className="w-3 h-3 mr-1" />
                        Verified
                      </Badge>
                    )}
                  </h1>
                  {businessName && (
                    <p className="text-sm font-medium text-muted-foreground mt-0.5">
                      {businessName}
                    </p>
                  )}
                  {!businessName && seller.is_seller && (
                    <p className="text-sm text-muted-foreground mt-0.5">@{seller.username}</p>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-2 sm:ml-auto mt-4 sm:mt-0">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="rounded-lg h-9 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/10"
                    onClick={() => setShowReportDialog(true)}
                  >
                    <Flag className="w-4 h-4 mr-1.5" />
                    Report
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-lg h-9"
                    onClick={handleMessageSeller}
                  >
                    <MessageSquare className="w-4 h-4 mr-1.5" />
                    Message
                  </Button>
                  {storeSlugForLink && (
                    <Button
                      variant="outline"
                      className="rounded-lg text-sm h-9"
                      onClick={() => router.push(routes.store(storeSlugForLink))}
                    >
                      <Store className="w-4 h-4 mr-1.5" />
                      View Store
                    </Button>
                  )}
                </div>
              </div>

              {/* Meta Info */}
              <div className="flex flex-wrap items-center gap-4 mt-4">
                {seller.profile?.city && (
                  <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <MapPin className="w-4 h-4" />
                    <span>{seller.profile.city}</span>
                  </div>
                )}
                <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <Calendar className="w-4 h-4" />
                  <span>Joined {formatDate(seller.date_joined)}</span>
                </div>
                {verificationStatus && verificationStatus !== 'unverified' && (
                  <Badge
                    variant="secondary"
                    className={`capitalize text-xs ${
                      verificationStatus === 'verified'
                        ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                        : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                    }`}
                  >
                    {verificationStatus}
                  </Badge>
                )}
              </div>

              {/* Bio */}
              {seller.profile?.bio && (
                <p className="text-sm text-muted-foreground mt-3 max-w-2xl">
                  {seller.profile.bio}
                </p>
              )}
            </div>
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mt-6 pt-6 border-t">
            <div className="text-center p-3 rounded-xl bg-muted/50">
              <div className="text-xl font-bold text-foreground">{totalCount}</div>
              <div className="text-xs text-muted-foreground">Listings</div>
            </div>
            <div className="text-center p-3 rounded-xl bg-muted/50">
              <div className="text-xl font-bold text-foreground flex items-center justify-center gap-1">
                <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
                —
              </div>
              <div className="text-xs text-muted-foreground">Avg Rating</div>
            </div>
            <div className="text-center p-3 rounded-xl bg-muted/50 hidden sm:block">
              <div className="text-xl font-bold text-foreground">
                {isVerifiedSeller ? 'Active' : 'New'}
              </div>
              <div className="text-xs text-muted-foreground">Status</div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Seller Listings */}
      <section>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-foreground">
            {fullName}&apos;s Products
          </h2>
          <span className="text-sm text-muted-foreground">{totalCount} items</span>
        </div>

        {listings.length === 0 ? (
          <EmptyState
            icon={Package}
            title="No products listed"
            description="This seller hasn't listed any products yet."
            actionLabel="Browse Marketplace"
            onAction={() => router.push(routes.home())}
          />
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 md:gap-6">
              {listings.map((listing) => (
                <ProductCard key={listing.id} listing={listing} onSelect={handleProductSelect} />
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
        )}
      </section>
      
      {/* Report Dialog */}
      <Dialog open={showReportDialog} onOpenChange={setShowReportDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600">
              <Flag className="w-5 h-5" />
              Report Seller
            </DialogTitle>
            <DialogDescription>
              Please tell us why you are reporting this seller. Our moderation team will investigate.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="report-reason">Reason</Label>
              <select
                id="report-reason"
                className="w-full h-10 px-3 rounded-lg border bg-background text-sm focus:ring-2 focus:ring-primary/20 outline-none"
                value={reportReason}
                onChange={(e) => setReportReason(e.target.value as any)}
              >
                <option value="fraud">Fraud / Scammer</option>
                <option value="spam">Spam / Multiple Listings</option>
                <option value="harassment">Harassment / Abusive</option>
                <option value="misleading">Misleading / Wrong info</option>
                <option value="inappropriate">Inappropriate content</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="report-text">Details</Label>
              <Textarea
                id="report-text"
                placeholder="Provide more details about the issue..."
                value={reportText}
                onChange={(e) => setReportText(e.target.value)}
                rows={4}
                className="rounded-xl resize-none"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowReportDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              className="rounded-lg"
              onClick={submitReport}
              disabled={isReporting || !reportText.trim()}
            >
              {isReporting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Submitting...
                </>
              ) : (
                <>
                  <Flag className="w-4 h-4 mr-2" />
                  Submit Report
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
