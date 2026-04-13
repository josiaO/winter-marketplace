'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Search,
  ShieldCheck,
  Truck,
  Headphones,
  Lock,
  ChevronRight,
  Sparkles,
  Clock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { CategoryBar } from '@/components/smartdalali/category-bar';
import { ProductCard } from '@/components/smartdalali/product-card';
import { SkeletonGrid } from '@/components/smartdalali/skeleton-grid';
import { useRouter } from 'next/navigation';
import { useUIStore } from '@/store';
import { routes } from '@/lib/routes';
import { api } from '@/lib/api-client';
import type { Listing, Category, PaginatedResponse } from '@/types/api';

export function HomePage() {
  const router = useRouter();
  const { searchQuery, setSearchQuery, setSelectedCategory } = useUIStore();

  const [categories, setCategories] = useState<Category[]>([]);
  const [featuredProducts, setFeaturedProducts] = useState<Listing[]>([]);
  const [newArrivals, setNewArrivals] = useState<Listing[]>([]);

  const [isLoadingCategories, setIsLoadingCategories] = useState(true);
  const [isLoadingFeatured, setIsLoadingFeatured] = useState(true);
  const [isLoadingNew, setIsLoadingNew] = useState(true);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const q = searchQuery.trim();
      router.push(routes.marketplace(q));
    },
    [searchQuery, router]
  );

  const handleCategorySelect = useCallback(
    (slug: string | null) => {
      setSelectedCategory(slug);
      if (slug) {
        router.push(routes.category(slug));
      }
    },
    [router, setSelectedCategory]
  );

  useEffect(() => {
    async function loadData() {
      try {
        // Fetch categories (tree format returns array of categories with children)
        const catRes = await api.catalog.categories({ tree: true });
        const cats: Category[] = Array.isArray(catRes) ? catRes : (catRes as PaginatedResponse<Category>).results || [];
        // Flatten: get top-level categories + their children if any
        const flatCats = cats.flatMap((c) => [c, ...(c.children || [])]);
        setCategories(flatCats);
      } catch {
        // Categories failed — continue with other fetches
      } finally {
        setIsLoadingCategories(false);
      }

      try {
        // Featured products
        const featuredRes = await api.listings.list({ is_featured: true });
        setFeaturedProducts(featuredRes.results || []);
      } catch {
        setFeaturedProducts([]);
      } finally {
        setIsLoadingFeatured(false);
      }

      try {
        // New arrivals
        const newRes = await api.listings.list({ ordering: '-created_at' });
        setNewArrivals(newRes.results || []);
      } catch {
        setNewArrivals([]);
      } finally {
        setIsLoadingNew(false);
      }
    }
    loadData();
  }, []);

  const handleProductSelect = useCallback(
    (listing: Listing) => {
      router.push(routes.product(String(listing.id)));
    },
    [router]
  );

  const fadeInUp = {
    initial: { opacity: 0, y: 20 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.5, ease: 'easeOut' as const },
  };

  return (
    <div className="flex flex-col">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-emerald-600 via-teal-600 to-cyan-700">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-10 left-10 w-72 h-72 bg-white rounded-full blur-3xl" />
          <div className="absolute bottom-10 right-10 w-96 h-96 bg-yellow-300 rounded-full blur-3xl" />
        </div>
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20 lg:py-28">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: 'easeOut' }}
            className="text-center max-w-3xl mx-auto"
          >
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-white tracking-tight mb-4">
              Discover Tanzania&apos;s{' '}
              <span className="text-yellow-300">Marketplace</span>
            </h1>
            <p className="text-base sm:text-lg text-emerald-100 mb-8 max-w-xl mx-auto">
              Buy and sell anything from electronics to fashion. Trusted sellers, secure payments, and nationwide delivery.
            </p>

            {/* Search Bar */}
            <form onSubmit={handleSearch} className="max-w-lg mx-auto relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <Input
                type="search"
                placeholder="Search products, brands, categories..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-12 pr-32 h-12 sm:h-14 rounded-full text-base bg-white/95 backdrop-blur-sm border-0 shadow-lg focus-visible:ring-2 focus-visible:ring-yellow-300"
              />
              <Button
                type="submit"
                className="absolute right-1.5 top-1/2 -translate-y-1/2 h-9 sm:h-10 px-4 sm:px-6 rounded-full bg-emerald-700 hover:bg-emerald-800 text-white font-medium"
              >
                Search
              </Button>
            </form>

            {/* Quick Links */}
            <div className="flex flex-wrap items-center justify-center gap-2 mt-6">
              {['Electronics', 'Fashion', 'Vehicles', 'Phones'].map((tag) => (
                <button
                  key={tag}
                  onClick={() => {
                    setSearchQuery(tag);
                    router.push(routes.marketplace(tag));
                  }}
                  className="px-3 py-1.5 text-sm text-emerald-100 bg-white/15 hover:bg-white/25 rounded-full transition-colors backdrop-blur-sm"
                >
                  {tag}
                </button>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* Category Bar */}
      <section className="border-b bg-background sticky top-16 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
          {isLoadingCategories ? (
            <div className="flex items-center gap-2 overflow-hidden">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-9 w-24 rounded-full flex-shrink-0" />
              ))}
            </div>
          ) : (
            <CategoryBar
              categories={categories}
              selectedCategory={null}
              onSelect={handleCategorySelect}
            />
          )}
        </div>
      </section>

      {/* Featured Products */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
        <motion.div {...fadeInUp}>
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-amber-500" />
              <h2 className="text-xl sm:text-2xl font-bold text-foreground">Featured Products</h2>
            </div>
            <Button
              variant="ghost"
              className="text-sm font-medium text-primary hover:text-primary/80 rounded-full"
              onClick={() => router.push(routes.marketplace())}
            >
              View All
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
          {isLoadingFeatured ? (
            <SkeletonGrid />
          ) : featuredProducts.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">No featured products available yet.</p>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-6">
              {featuredProducts.map((listing) => (
                <ProductCard
                  key={listing.id}
                  listing={listing}
                  onSelect={handleProductSelect}
                  density="compact"
                  showCartControls={false}
                />
              ))}
            </div>
          )}
        </motion.div>
      </section>

      {/* New Arrivals */}
      <section className="bg-muted/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
          <motion.div {...fadeInUp}>
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-emerald-500" />
                <h2 className="text-xl sm:text-2xl font-bold text-foreground">New Arrivals</h2>
              </div>
              <Button
                variant="ghost"
                className="text-sm font-medium text-primary hover:text-primary/80 rounded-full"
                onClick={() => router.push(routes.marketplace())}
              >
                View All
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
            {isLoadingNew ? (
              <SkeletonGrid />
            ) : newArrivals.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">No new arrivals yet.</p>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-6">
                {newArrivals.map((listing) => (
                  <ProductCard
                    key={listing.id}
                    listing={listing}
                    onSelect={handleProductSelect}
                    density="compact"
                    showCartControls={false}
                  />
                ))}
              </div>
            )}
          </motion.div>
        </div>
      </section>

      {/* Trust Badges */}
      <section className="border-t bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
          <motion.div {...fadeInUp}>
            <h2 className="text-xl sm:text-2xl font-bold text-foreground text-center mb-8">
              Why SmartDalali?
            </h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
              {[
                {
                  icon: Lock,
                  title: 'Escrow Protection',
                  description: 'Your money is held safely until you confirm delivery',
                  color: 'text-emerald-600',
                  bg: 'bg-emerald-100 dark:bg-emerald-900/30',
                },
                {
                  icon: Truck,
                  title: 'Fast Delivery',
                  description: 'Nationwide shipping to your doorstep',
                  color: 'text-teal-600',
                  bg: 'bg-teal-100 dark:bg-teal-900/30',
                },
                {
                  icon: ShieldCheck,
                  title: 'Buyer Protection',
                  description: 'Full refund if item is not as described',
                  color: 'text-amber-600',
                  bg: 'bg-amber-100 dark:bg-amber-900/30',
                },
                {
                  icon: Headphones,
                  title: '24/7 Support',
                  description: 'Round-the-clock customer assistance',
                  color: 'text-rose-600',
                  bg: 'bg-rose-100 dark:bg-rose-900/30',
                },
              ].map((badge, i) => (
                <motion.div
                  key={badge.title}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: i * 0.1 }}
                  className="flex flex-col items-center text-center p-4 sm:p-6 rounded-xl bg-background border"
                >
                  <div className={`w-12 h-12 rounded-full ${badge.bg} flex items-center justify-center mb-3`}>
                    <badge.icon className={`w-6 h-6 ${badge.color}`} />
                  </div>
                  <h3 className="font-semibold text-sm sm:text-base text-foreground mb-1">
                    {badge.title}
                  </h3>
                  <p className="text-xs sm:text-sm text-muted-foreground">
                    {badge.description}
                  </p>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
