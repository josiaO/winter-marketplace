'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Crown,
  ArrowUpRight,
  CheckCircle2,
  Star,
  Sparkles,
  Package,
  Clock,
  Tag,
  LayoutGrid,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS } from '@/lib/helpers';
import type { Plan, Feature, PaginatedResponse } from '@/types/api';

function getFeatureTypeConfig(type: Feature['type']) {
  switch (type) {
    case 'listing':
      return {
        color: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
        icon: Package,
        label: 'Listing',
      };
    case 'store':
      return {
        color: 'bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-400',
        icon: LayoutGrid,
        label: 'Store',
      };
    case 'promotion':
      return {
        color: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
        icon: Sparkles,
        label: 'Promotion',
      };
    default:
      return {
        color: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
        icon: Tag,
        label: type,
      };
  }
}

export function AdminPlansPage() {
  const { navigate } = useUIStore();
  const { user, isAuthenticated } = useAuthStore();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [features, setFeatures] = useState<Feature[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      navigate({ view: 'home' });
      return;
    }

    async function loadData() {
      try {
        const [plansRes, featuresRes] = await Promise.all([
          api.features.plansList(),
          api.features.featuresList(),
        ]);
        setPlans(plansRes.results);
        setFeatures(featuresRes.results);
      } catch {
        toast.error('Failed to load plans and features.');
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, [isAuthenticated, user, navigate]);

  if (!isAuthenticated || !user || user.role !== 'admin') return null;

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
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center gap-2">
              <Crown className="w-7 h-7 text-emerald-600" />
              Plans & Features
            </h1>
            <p className="text-muted-foreground mt-1">
              Manage subscription plans and platform features
            </p>
          </div>
          <Button
            variant="outline"
            className="gap-2 shrink-0"
            onClick={() => navigate({ view: 'admin-dashboard' })}
          >
            <ArrowUpRight className="w-4 h-4" />
            Back to Dashboard
          </Button>
        </motion.div>

        {/* Plans Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Crown className="w-5 h-5 text-emerald-600" />
                    Subscription Plans
                  </CardTitle>
                  <CardDescription className="mt-1">
                    {plans.length} plan{plans.length !== 1 ? 's' : ''} configured
                  </CardDescription>
                </div>
                <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 text-xs">
                  Active
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-72 w-full rounded-xl" />
                  ))}
                </div>
              ) : plans.length === 0 ? (
                <div className="text-center py-16">
                  <Crown className="w-12 h-12 mx-auto mb-3 text-muted-foreground/30" />
                  <h3 className="font-semibold text-foreground text-lg mb-1">No plans yet</h3>
                  <p className="text-sm text-muted-foreground">
                    Subscription plans will appear here once configured.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {plans.map((plan, index) => {
                    const typeConfig = plan.is_featured
                      ? { color: 'text-emerald-600 dark:text-emerald-400' }
                      : { color: 'text-muted-foreground' };

                    return (
                      <motion.div
                        key={plan.id}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.05 * index }}
                      >
                        <Card
                          className={`relative overflow-hidden h-full transition-all hover:shadow-lg ${
                            plan.is_featured
                              ? 'border-2 border-emerald-500 shadow-lg shadow-emerald-500/10'
                              : 'border shadow-sm'
                          }`}
                        >
                          {plan.is_featured && (
                            <div className="absolute top-0 right-0 bg-emerald-500 text-white text-[10px] font-bold px-2.5 py-1 rounded-bl-lg flex items-center gap-1">
                              <Sparkles className="w-3 h-3" />
                              FEATURED
                            </div>
                          )}
                          <CardHeader className="pb-2">
                            <CardTitle className="text-base flex items-center gap-2">
                              {plan.name}
                              {plan.is_featured && (
                                <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
                              )}
                            </CardTitle>
                            <CardDescription className="text-xs font-mono">
                              {plan.slug}
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            {/* Price */}
                            <div>
                              <p className="text-3xl font-bold text-foreground">
                                {formatTZS(plan.price)}
                              </p>
                              <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                per {plan.duration_days} days
                              </p>
                            </div>

                            <Separator />

                            {/* Plan limits */}
                            <div className="space-y-3">
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center shrink-0">
                                  <Package className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                                </div>
                                <div>
                                  <p className="text-sm font-medium">{plan.listing_limit}</p>
                                  <p className="text-[10px] text-muted-foreground">Listing Limit</p>
                                </div>
                              </div>
                              <div className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-lg bg-teal-100 dark:bg-teal-900/30 flex items-center justify-center shrink-0">
                                  <Sparkles className="w-4 h-4 text-teal-600 dark:text-teal-400" />
                                </div>
                                <div>
                                  <p className="text-sm font-medium">{plan.feature_limit}</p>
                                  <p className="text-[10px] text-muted-foreground">Feature Limit</p>
                                </div>
                              </div>
                            </div>

                            {/* Description */}
                            {plan.description && (
                              <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                                {plan.description}
                              </p>
                            )}
                          </CardContent>
                        </Card>
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* Features Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-emerald-600" />
                    Platform Features
                  </CardTitle>
                  <CardDescription className="mt-1">
                    Features available for subscription plans
                  </CardDescription>
                </div>
                <Badge variant="secondary" className="bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-400 text-xs">
                  {features.length} feature{features.length !== 1 ? 's' : ''}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} className="h-14 w-full" />
                  ))}
                </div>
              ) : features.length === 0 ? (
                <div className="text-center py-12">
                  <Sparkles className="w-10 h-10 mx-auto mb-2 text-muted-foreground/30" />
                  <h3 className="font-semibold text-foreground text-lg mb-1">No features configured</h3>
                  <p className="text-sm text-muted-foreground">
                    Platform features will appear here once configured.
                  </p>
                </div>
              ) : (
                <>
                  {/* Desktop Table */}
                  <div className="hidden md:block overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Feature</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Description</TableHead>
                          <TableHead className="text-right">Price</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {features.map((feature) => {
                          const typeConfig = getFeatureTypeConfig(feature.type);
                          const TypeIcon = typeConfig.icon;
                          return (
                            <TableRow key={feature.id}>
                              <TableCell>
                                <div className="flex items-center gap-2.5">
                                  <div
                                    className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${typeConfig.color}`}
                                  >
                                    <TypeIcon className="w-4 h-4" />
                                  </div>
                                  <div>
                                    <span className="text-sm font-medium">{feature.name}</span>
                                    <p className="text-[10px] text-muted-foreground font-mono">
                                      {feature.slug}
                                    </p>
                                  </div>
                                </div>
                              </TableCell>
                              <TableCell>
                                <Badge
                                  variant="secondary"
                                  className={`text-xs capitalize ${typeConfig.color}`}
                                >
                                  {typeConfig.label}
                                </Badge>
                              </TableCell>
                              <TableCell className="text-sm text-muted-foreground max-w-[300px] truncate">
                                {feature.description}
                              </TableCell>
                              <TableCell className="text-right text-sm font-semibold">
                                {formatTZS(feature.price)}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>

                  {/* Mobile Cards */}
                  <div className="md:hidden space-y-3">
                    {features.map((feature) => {
                      const typeConfig = getFeatureTypeConfig(feature.type);
                      const TypeIcon = typeConfig.icon;
                      return (
                        <div
                          key={feature.id}
                          className="border rounded-lg p-4 space-y-3"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-2.5">
                              <div
                                className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${typeConfig.color}`}
                              >
                                <TypeIcon className="w-4 h-4" />
                              </div>
                              <div>
                                <p className="text-sm font-medium">{feature.name}</p>
                                <p className="text-[10px] text-muted-foreground font-mono">
                                  {feature.slug}
                                </p>
                              </div>
                            </div>
                            <Badge
                              variant="secondary"
                              className={`text-xs capitalize shrink-0 ${typeConfig.color}`}
                            >
                              {typeConfig.label}
                            </Badge>
                          </div>
                          {feature.description && (
                            <p className="text-xs text-muted-foreground leading-relaxed">
                              {feature.description}
                            </p>
                          )}
                          <div className="flex items-center justify-between pt-1 border-t">
                            <span className="text-[10px] text-muted-foreground">Price</span>
                            <span className="text-sm font-bold">{formatTZS(feature.price)}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
