'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Package,
  Search,
  ArrowUpRight,
  Loader2,
  CheckCircle2,
  Star,
  Eye,
  MoreHorizontal,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, getRelativeTime } from '@/lib/helpers';
import { EmptyState } from '@/components/smartdalali/empty-state';
import type { Listing, PaginatedResponse } from '@/types/api';

const PAGE_SIZE = 20;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusBadgeClass(status: string) {
  switch (status) {
    case 'active':
    case 'published':
      return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400';
    case 'draft':
      return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400';
    case 'archived':
      return 'bg-gray-100 text-gray-600 dark:bg-gray-900/30 dark:text-gray-400';
    default:
      return 'bg-muted text-muted-foreground';
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AdminListingsPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const [listings, setListings] = useState<Listing[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [togglingAction, setTogglingAction] = useState<string | null>(null);

  // ── Data fetching ──────────────────────────────────────────────────────
  const fetchListings = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Record<string, string | number> = { page, limit: PAGE_SIZE };
      if (search) params.search = search;
      if (statusFilter !== 'all') {
        params.status = statusFilter === 'published' ? 'active' : statusFilter;
      }

      const res: PaginatedResponse<Listing> = await api.listings.list(params);
      setListings(res.results);
      setTotalCount(res.count);
    } catch {
      toast.error('Failed to load listings.');
    } finally {
      setIsLoading(false);
    }
  }, [search, statusFilter, page]);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      router.push(routes.home());
      return;
    }
    fetchListings();
  }, [isAuthenticated, user, router, fetchListings]);

  // ── Actions ────────────────────────────────────────────────────────────
  const handleToggleVerified = async (id: number) => {
    setTogglingId(id);
    setTogglingAction('verified');
    try {
      await api.listings.toggleVerified(id);
      toast.success('Listing verified status updated.');
      fetchListings();
    } catch {
      toast.error('Failed to update listing verification.');
    } finally {
      setTogglingId(null);
      setTogglingAction(null);
    }
  };

  const handleToggleFeatured = async (id: number) => {
    setTogglingId(id);
    setTogglingAction('featured');
    try {
      await api.listings.toggleFeatured(id);
      toast.success('Listing featured status updated.');
      fetchListings();
    } catch {
      toast.error('Failed to update listing featured status.');
    } finally {
      setTogglingId(null);
      setTogglingAction(null);
    }
  };

  // ── Guard ──────────────────────────────────────────────────────────────
  if (!isAuthenticated || !user || user.role !== 'admin') return null;

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  return (
    <div className="min-h-[80vh] px-4 py-6 sm:py-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* ── Header ─────────────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center gap-2">
              <Package className="w-7 h-7 text-emerald-600" />
              Listings Management
            </h1>
            <p className="text-muted-foreground mt-1">
              Review, verify, and moderate marketplace listings
            </p>
          </div>
          <Button
            variant="outline"
            className="gap-2 shrink-0"
            onClick={() => router.push(routes.adminDashboard())}
          >
            <ArrowUpRight className="w-4 h-4" />
            Dashboard
          </Button>
        </motion.div>

        {/* ── Search + Status Tabs ───────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardContent className="p-4 space-y-4">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Search listings by title..."
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                  className="pl-9"
                />
              </div>

              {/* Status Tabs */}
              <Tabs value={statusFilter} onValueChange={(val) => { setStatusFilter(val); setPage(1); }}>
                <TabsList>
                  <TabsTrigger value="all">All</TabsTrigger>
                  <TabsTrigger value="published">Published</TabsTrigger>
                  <TabsTrigger value="draft">Draft</TabsTrigger>
                  <TabsTrigger value="archived">Archived</TabsTrigger>
                </TabsList>

                <TabsContent value={statusFilter} className="mt-4">
                  {isLoading ? (
                    <div className="space-y-3">
                      {Array.from({ length: 8 }).map((_, i) => (
                        <Skeleton key={i} className="h-14 w-full" />
                      ))}
                    </div>
                  ) : listings.length === 0 ? (
                    <EmptyState
                      icon={Package}
                      title="No listings found"
                      description="Try adjusting your search or filter to find what you're looking for."
                    />
                  ) : (
                    <>
                      {/* ── Desktop Table ──────────────────────────────────── */}
                      <div className="hidden lg:block overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Listing</TableHead>
                              <TableHead>Seller</TableHead>
                              <TableHead>Category</TableHead>
                              <TableHead>Price</TableHead>
                              <TableHead>Status</TableHead>
                              <TableHead>Verified</TableHead>
                              <TableHead>Featured</TableHead>
                              <TableHead>Date</TableHead>
                              <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {listings.map((listing) => {
                              const thumb = listing.images?.[0];
                              const isBusy = togglingId === listing.id;

                              return (
                                <TableRow key={listing.id}>
                                  <TableCell>
                                    <div className="flex items-center gap-3 min-w-0">
                                      {thumb ? (
                                        <div className="w-10 h-10 rounded-lg bg-muted overflow-hidden shrink-0">
                                          <img
                                            src={thumb.image || (thumb as Record<string, string>).url || ''}
                                            alt={listing.title}
                                            className="w-full h-full object-cover"
                                          />
                                        </div>
                                      ) : (
                                        <div className="w-10 h-10 rounded-lg bg-muted shrink-0 flex items-center justify-center">
                                          <Package className="w-4 h-4 text-muted-foreground/40" />
                                        </div>
                                      )}
                                      <p className="text-sm font-medium truncate max-w-[200px]">
                                        {listing.title}
                                      </p>
                                    </div>
                                  </TableCell>
                                  <TableCell className="text-sm">
                                    {listing.seller?.username || 'Unknown'}
                                  </TableCell>
                                  <TableCell className="text-sm text-muted-foreground">
                                    {listing.category?.name || 'N/A'}
                                  </TableCell>
                                  <TableCell className="text-sm font-medium">
                                    {formatTZS(listing.price)}
                                  </TableCell>
                                  <TableCell>
                                    <Badge
                                      variant="secondary"
                                      className={`text-xs capitalize ${statusBadgeClass(listing.status)}`}
                                    >
                                      {listing.status}
                                    </Badge>
                                  </TableCell>
                                  <TableCell>
                                    {listing.is_verified ? (
                                      <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 text-xs gap-1">
                                        <ShieldCheck className="w-3 h-3" /> Verified
                                      </Badge>
                                    ) : (
                                      <Badge variant="secondary" className="text-xs text-muted-foreground">
                                        Not Verified
                                      </Badge>
                                    )}
                                  </TableCell>
                                  <TableCell>
                                    {listing.is_featured ? (
                                      <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 text-xs gap-1">
                                        <Sparkles className="w-3 h-3" /> Featured
                                      </Badge>
                                    ) : (
                                      <span className="text-xs text-muted-foreground">—</span>
                                    )}
                                  </TableCell>
                                  <TableCell className="text-xs text-muted-foreground">
                                    {getRelativeTime(listing.created_at)}
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <DropdownMenu>
                                      <DropdownMenuTrigger asChild>
                                        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                          <MoreHorizontal className="w-4 h-4" />
                                        </Button>
                                      </DropdownMenuTrigger>
                                      <DropdownMenuContent align="end">
                                        <DropdownMenuItem
                                          onClick={() => router.push(routes.product(String(listing.id)))}
                                        >
                                          <Eye className="w-4 h-4 mr-2" />
                                          View Listing
                                        </DropdownMenuItem>
                                        <DropdownMenuSeparator />
                                        <DropdownMenuItem
                                          onClick={() => handleToggleVerified(listing.id)}
                                          disabled={isBusy && togglingAction === 'verified'}
                                        >
                                          {isBusy && togglingAction === 'verified' ? (
                                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                          ) : (
                                            <ShieldCheck className="w-4 h-4 mr-2" />
                                          )}
                                          {listing.is_verified ? 'Unverify' : 'Verify'}
                                        </DropdownMenuItem>
                                        <DropdownMenuItem
                                          onClick={() => handleToggleFeatured(listing.id)}
                                          disabled={isBusy && togglingAction === 'featured'}
                                        >
                                          {isBusy && togglingAction === 'featured' ? (
                                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                          ) : (
                                            <Star className="w-4 h-4 mr-2" />
                                          )}
                                          {listing.is_featured ? 'Unfeature' : 'Feature'}
                                        </DropdownMenuItem>
                                      </DropdownMenuContent>
                                    </DropdownMenu>
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </div>

                      {/* ── Mobile Cards ───────────────────────────────────── */}
                      <div className="lg:hidden space-y-3 max-h-[600px] overflow-y-auto">
                        {listings.map((listing) => {
                          const thumb = listing.images?.[0];

                          return (
                            <div key={listing.id} className="border rounded-lg p-4 space-y-3">
                              <div className="flex items-start gap-3">
                                {thumb ? (
                                  <div className="w-14 h-14 rounded-lg bg-muted overflow-hidden shrink-0">
                                    <img
                                      src={thumb.image || (thumb as Record<string, string>).url || ''}
                                      alt={listing.title}
                                      className="w-full h-full object-cover"
                                    />
                                  </div>
                                ) : (
                                  <div className="w-14 h-14 rounded-lg bg-muted shrink-0 flex items-center justify-center">
                                    <Package className="w-5 h-5 text-muted-foreground/40" />
                                  </div>
                                )}
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm font-medium truncate">{listing.title}</p>
                                  <p className="text-xs text-muted-foreground">
                                    {listing.seller?.username || 'Unknown'} &middot; {listing.category?.name || 'N/A'}
                                  </p>
                                  <p className="text-sm font-bold mt-1">{formatTZS(listing.price)}</p>
                                </div>
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild>
                                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0 shrink-0">
                                      <MoreHorizontal className="w-4 h-4" />
                                    </Button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end">
                                    <DropdownMenuItem
                                      onClick={() => handleToggleVerified(listing.id)}
                                      disabled={togglingId === listing.id && togglingAction === 'verified'}
                                    >
                                      <ShieldCheck className="w-4 h-4 mr-2" />
                                      {listing.is_verified ? 'Unverify' : 'Verify'}
                                    </DropdownMenuItem>
                                    <DropdownMenuItem
                                      onClick={() => handleToggleFeatured(listing.id)}
                                      disabled={togglingId === listing.id && togglingAction === 'featured'}
                                    >
                                      <Star className="w-4 h-4 mr-2" />
                                      {listing.is_featured ? 'Unfeature' : 'Feature'}
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </div>
                              <div className="flex items-center gap-2 flex-wrap">
                                <Badge
                                  variant="secondary"
                                  className={`text-xs capitalize ${statusBadgeClass(listing.status)}`}
                                >
                                  {listing.status}
                                </Badge>
                                {listing.is_verified && (
                                  <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 text-xs gap-1">
                                    <ShieldCheck className="w-3 h-3" /> Verified
                                  </Badge>
                                )}
                                {listing.is_featured && (
                                  <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 text-xs gap-1">
                                    <Sparkles className="w-3 h-3" /> Featured
                                  </Badge>
                                )}
                                <span className="text-[10px] text-muted-foreground ml-auto">
                                  {getRelativeTime(listing.created_at)}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* ── Pagination ──────────────────────────────────────── */}
                      {totalPages > 1 && (
                        <div className="flex items-center justify-between mt-4 pt-4 border-t">
                          <p className="text-sm text-muted-foreground">
                            Page {page} of {totalPages} &middot; {totalCount} listings
                          </p>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={page <= 1}
                              onClick={() => setPage((p) => p - 1)}
                            >
                              <ChevronLeft className="w-4 h-4" />
                              Previous
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={page >= totalPages}
                              onClick={() => setPage((p) => p + 1)}
                            >
                              Next
                              <ChevronRight className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
