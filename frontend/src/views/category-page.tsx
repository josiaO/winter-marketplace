'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Home, Package, ChevronRight, Tag, LayoutGrid, List } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
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
import { useUIStore } from '@/store';
import { api } from '@/lib/api-client';
import { normalizeMediaUrl } from '@/lib/helpers';
import type { Listing, Category, PaginatedResponse } from '@/types/api';

const SORT_OPTIONS = [
  { value: '-created_at', label: 'Newest First' },
  { value: '-price', label: 'Price: High to Low' },
  { value: 'price', label: 'Price: Low to High' },
  { value: '-view_count', label: 'Most Popular' },
];

export function CategoryPage({ categorySlug }: { categorySlug: string }) {
  const router = useRouter();
  const slug = categorySlug;
  const { browseLayout, browseDensity, setBrowseLayout } = useUIStore();

  const [category, setCategory] = useState<Category | null>(null);
  const [listings, setListings] = useState<Listing[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [sortBy, setSortBy] = useState('-created_at');
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  // Reset page on sort or slug change
  useEffect(() => {
    setPage(1);
  }, [sortBy, slug]);

  const fetchCategoryData = useCallback(async () => {
    if (!slug) return;
    setIsLoading(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });

    try {
      // Fetch category detail
      const cat = await api.catalog.categoryDetail(slug);
      setCategory(cat);

      // Fetch listings for this category
      const res = await api.listings.list({
        category: cat.id,
        ordering: sortBy,
        page,
      });
      setListings(res.results || []);
      setTotalCount(res.count || 0);
      setHasMore(!!res.next);
    } catch {
      setListings([]);
      toast.error?.('Failed to load category');
    } finally {
      setIsLoading(false);
    }
  }, [slug, page, sortBy]);

  useEffect(() => {
    fetchCategoryData();
  }, [fetchCategoryData]);

  const handleProductSelect = useCallback(
    (listing: Listing) => router.push(routes.product(String(listing.id))),
    [router]
  );

  if (isLoading && !category) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-4 w-48 mb-6" />
        <Skeleton className="h-12 w-64 mb-2" />
        <Skeleton className="h-4 w-96 mb-8" />
        <SkeletonGrid />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        {/* Breadcrumb */}
        <Breadcrumb className="mb-4">
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
            {category?.parent && (
              <>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage className="text-sm text-muted-foreground">
                    Parent Category
                  </BreadcrumbPage>
                </BreadcrumbItem>
              </>
            )}
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage className="text-sm font-medium">
                {category?.name || slug}
              </BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>

        {/* Category Header */}
        <div className="flex flex-col sm:flex-row gap-6 mb-8">
          {category?.image && (
            <div className="relative w-full sm:w-48 h-32 sm:h-36 rounded-xl overflow-hidden bg-muted flex-shrink-0">
              <Image
                src={category.image}
                alt={category.name}
                fill
                className="object-cover"
              />
            </div>
          )}
          <div className="flex-1">
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
              {category?.name || slug}
            </h1>
            {category?.description && (
              <p className="text-sm text-muted-foreground mt-1 max-w-2xl">{category.description}</p>
            )}
            {!isLoading && (
              <p className="text-sm text-muted-foreground mt-2">
                {totalCount} {totalCount === 1 ? 'product' : 'products'}
              </p>
            )}
          </div>
        </div>

        {/* Subcategories */}
        {category?.children && category.children.length > 0 && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold text-foreground mb-4">Subcategories</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {category.children.map((sub) => (
                <button
                  key={sub.id}
                  onClick={() => router.push(routes.category(sub.slug))}
                  className="flex items-center gap-3 p-3 rounded-xl border bg-card hover:bg-muted/50 transition-colors text-left"
                >
                  {sub.image ? (
                    <div className="w-10 h-10 rounded-lg overflow-hidden bg-muted flex-shrink-0 relative">
                      <Image src={normalizeMediaUrl(sub.image) || sub.image} alt={sub.name} fill className="object-cover" />
                    </div>
                  ) : (
                    <div className="w-10 h-10 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center flex-shrink-0">
                      <Tag className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                    </div>
                  )}
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{sub.name}</p>
                    <p className="text-xs text-muted-foreground">{sub.listing_count} items</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Sort + Results */}
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-foreground">Products</h2>
          <div className="flex items-center gap-2">
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
            <Select value={sortBy} onValueChange={setSortBy}>
              <SelectTrigger className="w-[180px] h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SORT_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Products Grid */}
        {isLoading && page === 1 ? (
          <SkeletonGrid />
        ) : listings.length === 0 ? (
          <EmptyState
            icon={Package}
            title="No products in this category"
            description="There are no products listed in this category yet. Check back later!"
            actionLabel="Browse All Categories"
            onAction={() => router.push(routes.home())}
          />
        ) : (
          <>
            {browseLayout === 'grid' ? (
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

            {/* Load More */}
            {hasMore && (
              <div className="flex justify-center mt-8">
                <Button
                  variant="outline"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={isLoading}
                  className="rounded-full px-8"
                >
                  {isLoading ? 'Loading...' : 'Load More'}
                </Button>
              </div>
            )}
          </>
        )}
      </motion.div>
    </div>
  );
}
