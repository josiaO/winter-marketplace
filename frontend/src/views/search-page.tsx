'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useLayoutEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Search,
  SlidersHorizontal,
  X,
  Package,
  LayoutGrid,
  List,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { ProductCard } from '@/components/smartdalali/product-card';
import { SkeletonGrid } from '@/components/smartdalali/skeleton-grid';
import { EmptyState } from '@/components/smartdalali/empty-state';
import { useUIStore } from '@/store';
import { api } from '@/lib/api-client';
import { toast } from 'sonner';
import type { Listing, Category, PaginatedResponse } from '@/types/api';

const SORT_OPTIONS = [
  { value: '-created_at', label: 'Newest First' },
  { value: '-price', label: 'Price: High to Low' },
  { value: 'price', label: 'Price: Low to High' },
  { value: '-view_count', label: 'Most Popular' },
];

const CONDITION_OPTIONS = [
  { value: 'new', label: 'New' },
  { value: 'used', label: 'Used' },
  { value: 'refurbished', label: 'Refurbished' },
];

const PAGE_SIZE = 24;

export function SearchPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    searchQuery,
    setSearchQuery,
    browseLayout,
    browseDensity,
    setBrowseLayout,
  } = useUIStore();
  const urlQ = searchParams.get('q');
  const query = urlQ !== null ? urlQ : searchQuery;

  const [results, setResults] = useState<Listing[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [selectedCondition, setSelectedCondition] = useState<string>('');
  const [selectedSort, setSelectedSort] = useState('-created_at');
  const [priceMin, setPriceMin] = useState('');
  const [priceMax, setPriceMax] = useState('');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [searchInput, setSearchInput] = useState(query);

  useLayoutEffect(() => {
    setPage(1);
  }, [query, selectedSort, selectedCategory, selectedCondition, priceMin, priceMax]);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    (async () => {
      try {
        const limit = PAGE_SIZE;
        const offset = (page - 1) * limit;
        const params: Record<string, string | number | boolean | null | undefined> = {
          search: query.trim() || undefined,
          category: selectedCategory || undefined,
          condition: selectedCondition || undefined,
          min_price: priceMin ? Number(priceMin) : undefined,
          max_price: priceMax ? Number(priceMax) : undefined,
          ordering: selectedSort,
          limit,
          offset,
        };

        const res = await api.listings.list(params);
        if (cancelled) return;
        const rows = res.results || [];
        setTotalCount(res.count || 0);
        setHasMore(!!res.next);
        setResults((prev) => {
          const combined = page === 1 ? rows : [...prev, ...rows];
          // Deduplicate by ID to prevent duplicate React keys
          return Array.from(new Map(combined.map((item) => [item.id, item])).values());
        });
      } catch {
        if (cancelled) return;
        toast.error('Failed to fetch results');
        if (page === 1) setResults([]);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [query, page, selectedSort, selectedCategory, selectedCondition, priceMin, priceMax]);

  useEffect(() => {
    setSearchInput(query);
  }, [query]);

  // Fetch categories for filter dropdown
  useEffect(() => {
    api.catalog
      .categories()
      .then((res) => {
        const cats: Category[] = Array.isArray(res) ? res : (res as PaginatedResponse<Category>).results || [];
        setCategories(cats);
      })
      .catch(() => {});
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = searchInput.trim();
    setSearchQuery(trimmed);
    router.push(routes.marketplace(trimmed));
  };

  const handleProductSelect = useCallback(
    (listing: Listing) => router.push(routes.product(String(listing.id))),
    [router]
  );

  const clearFilters = () => {
    setSelectedCategory('');
    setSelectedCondition('');
    setSelectedSort('-created_at');
    setPriceMin('');
    setPriceMax('');
  };

  const hasActiveFilters =
    !!selectedCategory || !!selectedCondition || selectedSort !== '-created_at' || !!priceMin || !!priceMax;

  const FilterContent = () => (
    <div className="space-y-6">
      {/* Category */}
      <div className="space-y-2">
        <Label>Category</Label>
        <Select value={selectedCategory} onValueChange={(v) => setSelectedCategory(v === '_all' ? '' : v)}>
          <SelectTrigger>
            <SelectValue placeholder="All Categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">All Categories</SelectItem>
            {categories.map((cat) => (
              <SelectItem key={cat.id} value={String(cat.id)}>
                {cat.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Condition */}
      <div className="space-y-2">
        <Label>Condition</Label>
        <Select value={selectedCondition} onValueChange={(v) => setSelectedCondition(v === '_all' ? '' : v)}>
          <SelectTrigger>
            <SelectValue placeholder="All Conditions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">All Conditions</SelectItem>
            {CONDITION_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Price Range */}
      <div className="space-y-2">
        <Label>Price Range (TZS)</Label>
        <div className="flex items-center gap-2">
          <Input
            placeholder="Min"
            type="number"
            value={priceMin}
            onChange={(e) => setPriceMin(e.target.value)}
            className="w-full"
          />
          <span className="text-muted-foreground">-</span>
          <Input
            placeholder="Max"
            type="number"
            value={priceMax}
            onChange={(e) => setPriceMax(e.target.value)}
            className="w-full"
          />
        </div>
      </div>

      {/* Sort */}
      <div className="space-y-2">
        <Label>Sort By</Label>
        <Select value={selectedSort} onValueChange={setSelectedSort}>
          <SelectTrigger>
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

      {hasActiveFilters && (
        <Button variant="ghost" className="w-full text-sm" onClick={clearFilters}>
          <X className="w-4 h-4 mr-1" />
          Clear All Filters
        </Button>
      )}
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Search Header */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6"
      >
        {/* Search Bar */}
        <form onSubmit={handleSearch} className="relative max-w-2xl mb-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search products..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full pl-10 pr-4 h-11 rounded-full"
          />
        </form>

        <div className="flex items-center justify-between">
          <div>
            {isLoading ? (
              <span className="text-sm text-muted-foreground">Loading...</span>
            ) : (
              <p className="text-sm text-muted-foreground">
                {query ? (
                  <>
                    Showing <span className="font-medium text-foreground">{totalCount}</span>{' '}
                    results for &ldquo;
                    <span className="font-medium text-foreground">{query}</span>&rdquo;
                  </>
                ) : (
                  <>
                    Showing <span className="font-medium text-foreground">{totalCount}</span>{' '}
                    products
                  </>
                )}
              </p>
            )}
          </div>

          {/* Desktop Sort */}
          <div className="hidden md:flex items-center gap-2">
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
            <Select value={selectedSort} onValueChange={setSelectedSort}>
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
      </motion.div>

      <div className="flex gap-6">
        {/* Desktop Sidebar */}
        <aside className="hidden lg:block w-64 flex-shrink-0">
          <div className="sticky top-24 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-foreground">Filters</h3>
              {hasActiveFilters && (
                <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={clearFilters}>
                  Clear all
                </Button>
              )}
            </div>
            <FilterContent />
          </div>
        </aside>

        {/* Results */}
        <div className="flex-1">
          {/* Mobile filter button */}
          <div className="flex md:hidden items-center gap-2 mb-4">
            <Sheet open={filtersOpen} onOpenChange={setFiltersOpen}>
              <SheetTrigger asChild>
                <Button variant="outline" size="sm" className="rounded-lg">
                  <SlidersHorizontal className="w-4 h-4 mr-1.5" />
                  Filters
                  {hasActiveFilters && (
                    <span className="ml-1.5 w-2 h-2 rounded-full bg-emerald-500" />
                  )}
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-80">
                <SheetHeader>
                  <SheetTitle>Filters</SheetTitle>
                </SheetHeader>
                <div className="mt-4">
                  <FilterContent />
                </div>
              </SheetContent>
            </Sheet>

            <Select value={selectedSort} onValueChange={setSelectedSort}>
              <SelectTrigger className="h-9 flex-1">
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

            <div className="flex items-center rounded-lg border bg-muted/30 p-1">
              <Button
                type="button"
                variant={browseLayout === 'grid' ? 'default' : 'ghost'}
                size="sm"
                className="h-7 w-9 rounded-md px-0"
                onClick={() => setBrowseLayout('grid')}
              >
                <LayoutGrid className="w-4 h-4" />
              </Button>
              <Button
                type="button"
                variant={browseLayout === 'list' ? 'default' : 'ghost'}
                size="sm"
                className="h-7 w-9 rounded-md px-0"
                onClick={() => setBrowseLayout('list')}
              >
                <List className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {isLoading && page === 1 ? (
            <SkeletonGrid />
          ) : results.length === 0 ? (
            <EmptyState
              icon={Search}
              title="No results found"
              description={
                query
                  ? `We couldn't find any products matching "${query}". Try different keywords or filters.`
                  : 'No products match your current filters.'
              }
              actionLabel="Clear Filters"
              onAction={clearFilters}
            />
          ) : (
            <>
              {browseLayout === 'grid' ? (
                <div className="grid grid-cols-2 sm:grid-cols-2 xl:grid-cols-3 gap-3 md:gap-6">
                  {results.map((listing) => (
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
                  {results.map((listing) => (
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
                          <p className="text-xs text-muted-foreground truncate">
                            {listing.city || ''}
                          </p>
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

              {/* Pagination */}
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
        </div>
      </div>
    </div>
  );
}
