'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
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
  Trash2,
  Plus,
  Minus,
  AlertTriangle,
  ChevronLeft,
  History,
  CheckCircle,
  Loader2,
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
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, formatDate } from '@/lib/helpers';
import { EmptyState } from '@/components/smartdalali/empty-state';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import type { Listing, PaginatedResponse } from '@/types/api';

export function SellerListingsPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [listings, setListings] = useState<Listing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table');
  
  // Deletion state
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [listingToDelete, setListingToDelete] = useState<Listing | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Stock update state
  const [isStockDialogOpen, setIsStockDialogOpen] = useState(false);
  const [listingToUpdateStock, setListingToUpdateStock] = useState<Listing | null>(null);
  const [newStock, setNewStock] = useState<number>(0);
  const [isUpdatingStock, setIsUpdatingStock] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push(routes.login());
      return;
    }
    if (!user?.is_seller) {
      toast.error('You must be a seller to view listings.');
      router.push(routes.home());
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
  }, [isAuthenticated, user, router]);

  const loadListings = async () => {
    setIsLoading(true);
    try {
      const data = await api.listings.sellerListings();
      const anyData = data as any;
      const items = (anyData?.results as Listing[] | undefined) ?? (Array.isArray(anyData) ? anyData : []);
      setListings((items as Listing[]) || []);
    } catch {
      toast.error('Failed to load your listings.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteListing = async () => {
    if (!listingToDelete) return;
    setIsDeleting(true);
    try {
      await api.listings.delete(String(listingToDelete.id));
      toast.success('Listing deleted successfully');
      setListings(prev => prev.filter(l => l.id !== listingToDelete.id));
      setIsDeleteDialogOpen(false);
    } catch (err) {
      toast.error('Failed to delete listing');
    } finally {
      setIsDeleting(false);
      setListingToDelete(null);
    }
  };

  const handleUpdateStock = async () => {
    if (!listingToUpdateStock) return;
    setIsUpdatingStock(true);
    try {
      await api.listings.update(String(listingToUpdateStock.id), {
        id: listingToUpdateStock.id,
        stock_quantity: newStock,
        track_inventory: true, // Ensure it's tracked if updating
      });
      toast.success('Stock updated');
      setListings(prev => prev.map(l => l.id === listingToUpdateStock.id ? { ...l, stock_quantity: newStock } : l));
      setIsStockDialogOpen(false);
    } catch (err) {
      toast.error('Failed to update stock');
    } finally {
      setIsUpdatingStock(false);
      setListingToUpdateStock(null);
    }
  };

  const toggleStatus = async (listing: Listing) => {
    const newStatus = listing.status === 'published' ? 'draft' : 'published';
    try {
      await api.listings.update(String(listing.id), {
        id: listing.id,
        status: newStatus,
        is_published: newStatus === 'published',
      });
      toast.success(`Listing ${newStatus === 'published' ? 'activated' : 'deactivated'}`);
      setListings(prev => prev.map(l => l.id === listing.id ? { ...l, status: newStatus } : l));
    } catch (err) {
      toast.error('Failed to update status');
    }
  };

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
    <div className="space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div className="flex items-center gap-4">
            <Button
              variant="outline"
              size="icon"
              className="rounded-full shadow-sm bg-white shrink-0"
              onClick={() => router.back()}
            >
              <ChevronLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-foreground">My Listings</h1>
              <p className="text-muted-foreground mt-1 text-sm sm:text-base">
                Manage your product listings
              </p>
            </div>
          </div>
          <Button className="gap-2 shrink-0 shadow-lg shadow-emerald-500/20" onClick={() => router.push(routes.sellerListingNew())}>
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
          <EmptyState
            icon={PackageX}
            title={searchQuery || statusFilter !== 'all' ? 'No matching listings' : 'No listings yet'}
            description={
              searchQuery || statusFilter !== 'all'
                ? 'Try adjusting your search or filter criteria.'
                : 'Start selling by adding your first product listing.'
            }
            actionLabel={!searchQuery && statusFilter === 'all' ? 'Add Your First Listing' : undefined}
            onAction={!searchQuery && statusFilter === 'all' ? () => router.push(routes.sellerListingCreate()) : undefined}
          />
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
                        <TableHead>Inventory</TableHead>
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
                              onClick={() => router.push(routes.product(String(listing.id)))}
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
                                {(listing as any).track_inventory !== false ? (
                                  <div 
                                    className="flex items-center gap-2 group/stock cursor-pointer"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setListingToUpdateStock(listing);
                                      setNewStock(listing.stock_quantity ?? 0);
                                      setIsStockDialogOpen(true);
                                    }}
                                  >
                                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                                      (listing.stock_quantity ?? 0) <= ((listing as any).low_stock_threshold ?? 5)
                                        ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                                        : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                                    }`}>
                                      {listing.stock_quantity ?? 0} in stock
                                    </span>
                                    <Edit3 className="w-3 h-3 opacity-0 group-hover/stock:opacity-100 transition-opacity" />
                                  </div>
                                ) : (
                                  <span className="text-xs text-muted-foreground italic">Unlimited</span>
                                )}
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
                                        router.push(routes.product(String(listing.id)));
                                      }}
                                    >
                                      <Eye className="w-4 h-4 mr-2" />
                                      View
                                    </DropdownMenuItem>
                                    <DropdownMenuItem
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        router.push(routes.sellerListingEdit(String(listing.id)));
                                      }}
                                    >
                                      <Edit3 className="w-4 h-4 mr-2" />
                                      Edit
                                    </DropdownMenuItem>
                                    <DropdownMenuSeparator />
                                    <DropdownMenuItem onClick={(e) => { e.stopPropagation(); toggleStatus(listing); }}>
                                      {listing.status === 'published' ? (
                                        <ToggleRight className="w-4 h-4 mr-2" />
                                      ) : (
                                        <ToggleLeft className="w-4 h-4 mr-2" />
                                      )}
                                      {listing.status === 'published' ? 'Deactivate' : 'Activate'}
                                    </DropdownMenuItem>
                                    <DropdownMenuItem
                                      className="text-destructive focus:text-destructive"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setListingToDelete(listing);
                                        setIsDeleteDialogOpen(true);
                                      }}
                                    >
                                      <Trash2 className="w-4 h-4 mr-2" />
                                      Delete
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
                      onClick={() => router.push(routes.product(String(listing.id)))}
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

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2 text-destructive">
                <AlertTriangle className="w-5 h-5" />
                Delete Listing?
              </AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete <strong>{listingToDelete?.title}</strong>? This action cannot be undone and will remove the product from the marketplace.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
              <AlertDialogAction
                disabled={isDeleting}
                onClick={(e) => {
                  e.preventDefault();
                  handleDeleteListing();
                }}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : "Delete Listing"}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Quick Stock Update Dialog */}
        <Dialog open={isStockDialogOpen} onOpenChange={setIsStockDialogOpen}>
          <DialogContent className="sm:max-w-[400px]">
            <DialogHeader>
              <DialogTitle>Update Stock</DialogTitle>
              <DialogDescription>
                Quickly adjust available quantity for this product.
              </DialogDescription>
            </DialogHeader>
            <div className="py-6 flex flex-col items-center justify-center gap-4">
              <div className="text-center">
                <p className="text-sm font-medium text-muted-foreground truncate max-w-[300px] mb-4">
                  {listingToUpdateStock?.title}
                </p>
                <div className="flex items-center gap-6">
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-12 w-12 rounded-full"
                    onClick={() => setNewStock(prev => Math.max(0, prev - 1))}
                  >
                    <Minus className="w-6 h-6" />
                  </Button>
                  <div className="text-center w-24">
                    <input
                      type="number"
                      value={newStock}
                      onChange={(e) => setNewStock(Math.max(0, parseInt(e.target.value) || 0))}
                      className="text-4xl font-bold bg-transparent text-center w-full focus:outline-none"
                    />
                    <p className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">Available Units</p>
                  </div>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-12 w-12 rounded-full"
                    onClick={() => setNewStock(prev => prev + 1)}
                  >
                    <Plus className="w-6 h-6" />
                  </Button>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setIsStockDialogOpen(false)} disabled={isUpdatingStock}>
                Cancel
              </Button>
              <Button onClick={handleUpdateStock} disabled={isUpdatingStock} className="gap-2">
                {isUpdatingStock ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                Save Changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
    </div>
  );
}
