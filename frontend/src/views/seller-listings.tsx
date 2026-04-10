'use client';

import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Package,
  Eye,
  Edit3,
  ToggleLeft,
  ToggleRight,
  ImageOff,
  PackageX,
  Grid3X3,
  List,
  MoreHorizontal,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, formatDate } from '@/lib/helpers';
import type { Listing, PaginatedResponse } from '@/types/api';

export function SellerListingsPage() {
  const { navigate } = useUIStore();
  const { user, isAuthenticated } = useAuthStore();
  const [listings, setListings] = useState<Listing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table');

  useEffect(() => {
    if (!isAuthenticated) {
      navigate({ view: 'login' });
      return;
    }
    if (!user?.is_seller) {
      toast.error('You must be a seller to view listings.');
      navigate({ view: 'home' });
      return;
    }

    async function loadListings() {
      try {
        const data = await api.listings.sellerListings();
        const anyData = data as any;
        const items = (anyData?.results as Listing[] | undefined) ?? (Array.isArray(anyData) ? anyData : []);
        // seller endpoint sometimes returns {results, count} without pagination wrapper
        setListings((items as Listing[]) || []);
      } catch {
        toast.error('Failed to load your listings.');
      } finally {
        setIsLoading(false);
      }
    }
    loadListings();
  }, [isAuthenticated, user, navigate]);

  const filteredListings = useMemo(() => {
    let filtered = listings;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (l) =>
          l.title.toLowerCase().includes(q) ||
          l.description.toLowerCase().includes(q) ||
          l.category.name.toLowerCase().includes(q)
      );
    }
    if (statusFilter !== 'all') {
      filtered = filtered.filter((l) => l.status === statusFilter);
    }
    return filtered;
  }, [listings, searchQuery, statusFilter]);

  // Stats
  const totalListings = listings.length;
  const publishedListings = listings.filter((l) => l.status === 'published').length;
  const draftListings = listings.filter((l) => l.status === 'draft').length;
  const archivedListings = listings.filter((l) => l.status === 'archived').length;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'published':
        return (
          <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs">
            Active
          </Badge>
        );
      case 'draft':
        return (
          <Badge className="bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 text-xs">
            Draft
          </Badge>
        );
      case 'archived':
        return (
          <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 text-xs">
            Archived
          </Badge>
        );
      default:
        return <Badge variant="secondary" className="text-xs">{status}</Badge>;
    }
  };

  const getListingImage = (listing: Listing) => {
    const primary = listing.images?.find((img) => img.is_primary) || listing.images?.[0];
    return primary?.image || null;
  };

  if (!isAuthenticated || !user) return null;

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">My Listings</h1>
            <p className="text-muted-foreground mt-1">
              Manage your product listings
            </p>
          </div>
          <Button className="gap-2 shrink-0" onClick={() => toast.info('Listing editor coming soon!')}>
            <Package className="w-4 h-4" />
            Add New Listing
          </Button>
        </motion.div>

        {/* Stats Summary */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Card className="border-0 shadow-sm">
            <CardContent className="p-3 sm:p-4 text-center">
              <p className="text-lg sm:text-2xl font-bold text-foreground">{totalListings}</p>
              <p className="text-xs text-muted-foreground">Total Listings</p>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-sm">
            <CardContent className="p-3 sm:p-4 text-center">
              <p className="text-lg sm:text-2xl font-bold text-green-600">{publishedListings}</p>
              <p className="text-xs text-muted-foreground">Active</p>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-sm">
            <CardContent className="p-3 sm:p-4 text-center">
              <p className="text-lg sm:text-2xl font-bold text-gray-500">{draftListings}</p>
              <p className="text-xs text-muted-foreground">Drafts</p>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-sm">
            <CardContent className="p-3 sm:p-4 text-center">
              <p className="text-lg sm:text-2xl font-bold text-red-500">{archivedListings}</p>
              <p className="text-xs text-muted-foreground">Archived</p>
            </CardContent>
          </Card>
        </div>

        {/* Search & Filters */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="flex flex-col sm:flex-row gap-3"
        >
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search listings..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 h-10"
            />
          </div>
          <div className="flex gap-2">
            {/* Status Filter Buttons */}
            <div className="flex rounded-lg border bg-muted/50 p-0.5 gap-0.5">
              {(['all', 'published', 'draft', 'archived'] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    statusFilter === status
                      ? 'bg-background shadow-sm text-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {status === 'all' ? 'All' : status.charAt(0).toUpperCase() + status.slice(1)}
                </button>
              ))}
            </div>
            {/* View Toggle */}
            <div className="flex rounded-lg border bg-muted/50 p-0.5">
              <button
                onClick={() => setViewMode('table')}
                className={`p-1.5 rounded-md transition-colors ${
                  viewMode === 'table'
                    ? 'bg-background shadow-sm text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <List className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-md transition-colors ${
                  viewMode === 'grid'
                    ? 'bg-background shadow-sm text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Grid3X3 className="w-4 h-4" />
              </button>
            </div>
          </div>
        </motion.div>

        {/* Listings Content */}
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : filteredListings.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <Card className="border-0 shadow-sm">
              <CardContent className="py-16 text-center">
                <PackageX className="w-12 h-12 mx-auto mb-3 text-muted-foreground/30" />
                <h3 className="font-semibold text-foreground text-lg mb-1">
                  {searchQuery || statusFilter !== 'all' ? 'No matching listings' : 'No listings yet'}
                </h3>
                <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                  {searchQuery || statusFilter !== 'all'
                    ? 'Try adjusting your search or filter criteria.'
                    : 'Start selling by adding your first product listing.'}
                </p>
                {!searchQuery && statusFilter === 'all' && (
                  <Button
                    className="mt-4 gap-2"
                    onClick={() => toast.info('Listing editor coming soon!')}
                  >
                    <Package className="w-4 h-4" />
                    Add Your First Listing
                  </Button>
                )}
              </CardContent>
            </Card>
          </motion.div>
        ) : viewMode === 'table' ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <Card className="border-0 shadow-md shadow-black/5">
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">Image</TableHead>
                        <TableHead>Product</TableHead>
                        <TableHead>Category</TableHead>
                        <TableHead className="text-right">Price</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="hidden sm:table-cell">Created</TableHead>
                        <TableHead className="w-12"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      <AnimatePresence>
                        {filteredListings.map((listing) => {
                          const imgUrl = getListingImage(listing);
                          return (
                            <motion.tr
                              key={listing.id}
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              exit={{ opacity: 0 }}
                              className="group cursor-pointer hover:bg-muted/50 border-b last:border-0"
                              onClick={() => navigate({ view: 'product', id: String(listing.id) })}
                            >
                              <TableCell className="py-3 px-4">
                                <div className="w-10 h-10 rounded-lg bg-muted overflow-hidden">
                                  {imgUrl ? (
                                    <img
                                      src={imgUrl}
                                      alt={listing.title}
                                      className="w-full h-full object-cover"
                                    />
                                  ) : (
                                    <div className="w-full h-full flex items-center justify-center">
                                      <ImageOff className="w-4 h-4 text-muted-foreground/40" />
                                    </div>
                                  )}
                                </div>
                              </TableCell>
                              <TableCell className="py-3 px-4">
                                <p className="text-sm font-medium text-foreground truncate max-w-[200px]">
                                  {listing.title}
                                </p>
                              </TableCell>
                              <TableCell className="py-3 px-4 hidden md:table-cell">
                                <span className="text-xs text-muted-foreground">
                                  {listing.category.name}
                                </span>
                              </TableCell>
                              <TableCell className="py-3 px-4 text-right">
                                <span className="text-sm font-semibold text-foreground">
                                  {formatTZS(listing.price)}
                                </span>
                              </TableCell>
                              <TableCell className="py-3 px-4">
                                {getStatusBadge(listing.status)}
                              </TableCell>
                              <TableCell className="py-3 px-4 hidden sm:table-cell">
                                <span className="text-xs text-muted-foreground">
                                  {formatDate(listing.created_at)}
                                </span>
                              </TableCell>
                              <TableCell className="py-3 px-4">
                                <DropdownMenu>
                                  <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                                    <Button variant="ghost" size="icon" className="h-8 w-8">
                                      <MoreHorizontal className="w-4 h-4" />
                                    </Button>
                                  </DropdownMenuTrigger>
                                  <DropdownMenuContent align="end">
                                    <DropdownMenuItem
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        navigate({ view: 'product', id: String(listing.id) });
                                      }}
                                    >
                                      <Eye className="w-4 h-4 mr-2" />
                                      View
                                    </DropdownMenuItem>
                                    <DropdownMenuItem
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        toast.info('Edit feature coming soon!');
                                      }}
                                    >
                                      <Edit3 className="w-4 h-4 mr-2" />
                                      Edit
                                    </DropdownMenuItem>
                                    <DropdownMenuItem
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        toast.info(
                                          listing.status === 'published'
                                            ? 'Product deactivated.'
                                            : 'Product activated.'
                                        );
                                      }}
                                    >
                                      {listing.status === 'published' ? (
                                        <ToggleRight className="w-4 h-4 mr-2" />
                                      ) : (
                                        <ToggleLeft className="w-4 h-4 mr-2" />
                                      )}
                                      {listing.status === 'published' ? 'Deactivate' : 'Activate'}
                                    </DropdownMenuItem>
                                  </DropdownMenuContent>
                                </DropdownMenu>
                              </TableCell>
                            </motion.tr>
                          );
                        })}
                      </AnimatePresence>
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ) : (
          /* Grid View */
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            <AnimatePresence>
              {filteredListings.map((listing) => {
                const imgUrl = getListingImage(listing);
                return (
                  <motion.div
                    key={listing.id}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                  >
                    <Card
                      className="border-0 shadow-md shadow-black/5 hover:shadow-lg transition-all cursor-pointer group overflow-hidden"
                      onClick={() => navigate({ view: 'product', id: String(listing.id) })}
                    >
                      <div className="aspect-square bg-muted relative overflow-hidden">
                        {imgUrl ? (
                          <img
                            src={imgUrl}
                            alt={listing.title}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <ImageOff className="w-8 h-8 text-muted-foreground/30" />
                          </div>
                        )}
                        <div className="absolute top-2 right-2">
                          {getStatusBadge(listing.status)}
                        </div>
                      </div>
                      <CardContent className="p-4">
                        <h3 className="text-sm font-semibold text-foreground truncate mb-1">
                          {listing.title}
                        </h3>
                        <p className="text-xs text-muted-foreground mb-2">
                          {listing.category.name}
                        </p>
                        <div className="flex items-center justify-between">
                          <span className="text-base font-bold text-primary">
                            {formatTZS(listing.price)}
                          </span>
                        </div>
                      </CardContent>
                    </Card>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}
