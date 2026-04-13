'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  DollarSign, ShoppingBag, Package, Clock, TrendingUp, PlusCircle,
  ClipboardList, Wallet, ArrowUpRight, BarChart3, Shield, Info,
  CheckCircle2, AlertTriangle, AlertCircle
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, formatDate, getStatusColor, getStatusLabel } from '@/lib/helpers';
import type { Order, SellerStats } from '@/types/api';

export function SellerDashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [dashboard, setDashboard] = useState<SellerStats | null>(null);
  const [progress, setProgress] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProgressLoading, setIsProgressLoading] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);
  const [openDisputes, setOpenDisputes] = useState(0);

  useEffect(() => {
    if (!isAuthenticated || !user?.is_seller) return;

    async function loadData() {
      try {
        const [stats, prog, unread, disputes] = await Promise.all([
          api.insights.sellerStats(),
          api.sellers.onboardingProgress(),
          api.communications.unreadCount(),
          api.escrow.disputes({ status: 'open' })
        ]);
        setDashboard(stats as SellerStats);
        setProgress(prog);
        setUnreadCount(unread.unread_count);
        setOpenDisputes(disputes.count);
      } catch {
        toast.error('Failed to load dashboard data.');
      } finally {
        setIsLoading(false);
        setIsProgressLoading(false);
      }
    }
    loadData();
  }, [isAuthenticated, user, router]);

  if (!isAuthenticated || !user) return null;

  const displayName = user.first_name || user.last_name
    ? [user.first_name, user.last_name].filter(Boolean).join(' ')
    : user.username;

  const revenueChart = dashboard?.revenue_chart ?? [];
  const maxRevenue = revenueChart.length ? Math.max(...revenueChart.map((m) => m.revenue), 1) : 1;
  const formatChartDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  // isStateA: true when onboarding is incomplete. false only when progress confirms all steps done.
  // Never false during initial load — prevents the banner from flashing away on reload.
  const isStateA = isProgressLoading ? true : (progress && (!progress.step_id_approved || !progress.step_payout_added));
  const showBusinessUpgrade = !isProgressLoading && progress && !progress.step_business_upgraded && ((dashboard?.total_revenue ?? 0) > 500000 || (dashboard?.total_orders ?? 0) >= 20);

  return (
    <div className="space-y-6">
        
        {/* Onboarding State A block */}
        <AnimatePresence>
          {isStateA && (
            <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="mb-6">
              <Card className="border-orange-200 bg-orange-50/50 dark:border-orange-900/50 dark:bg-orange-900/20 shadow-sm">
                <CardHeader className="pb-3">
                  <CardTitle className="text-orange-800 dark:text-orange-400 flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5" />
                    Complete Your Store Setup
                  </CardTitle>
                  <CardDescription className="text-orange-700/80 dark:text-orange-300/80">
                    You need to complete a few steps before your store is fully active and visible to buyers.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {isProgressLoading ? (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      <Skeleton className="h-28 rounded-xl" />
                      <Skeleton className="h-28 rounded-xl" />
                      <Skeleton className="h-28 rounded-xl" />
                    </div>
                  ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                     <div className={`p-4 rounded-xl border-2 ${progress.step_first_product ? 'border-green-200 bg-green-50/50' : 'border-orange-200 bg-white dark:bg-black/20'}`}>
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-semibold text-sm">1. First Product</h4>
                          {progress.step_first_product ? <CheckCircle2 className="w-5 h-5 text-green-500" /> : <div className="w-5 h-5 rounded-full border-2 border-orange-300" />}
                        </div>
                        <p className="text-xs text-muted-foreground mb-3">Add a product to your catalog.</p>
                        {!progress.step_first_product && (
                          <Button size="sm" variant="secondary" className="w-full" onClick={() => router.push(routes.sellerListingNew())}>Publish Product</Button>
                        )}
                     </div>

                     <div className={`p-4 rounded-xl border-2 ${progress.step_id_approved ? 'border-green-200 bg-green-50/50' : 'border-orange-200 bg-white dark:bg-black/20'}`}>
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-semibold text-sm">2. Verify Identity</h4>
                          {progress.step_id_approved ? <CheckCircle2 className="w-5 h-5 text-green-500" /> : <div className="w-5 h-5 rounded-full border-2 border-orange-300" />}
                        </div>
                        <p className="text-xs text-muted-foreground mb-3">Confirm your identity for trust.</p>
                        {!progress.step_id_approved ? (
                          <Button size="sm" variant="secondary" className="w-full" onClick={() => router.push(routes.sellerOnboardingVerifyIdentity())}>
                            {progress.step_id_submitted ? 'Under Review' : 'Verify Identity'}
                          </Button>
                        ) : null}
                     </div>

                     <div className={`p-4 rounded-xl border-2 ${progress.step_payout_added ? 'border-green-200 bg-green-50/50' : 'border-orange-200 bg-white dark:bg-black/20'}`}>
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="font-semibold text-sm">3. Payout Method</h4>
                          {progress.step_payout_added ? <CheckCircle2 className="w-5 h-5 text-green-500" /> : <div className="w-5 h-5 rounded-full border-2 border-orange-300" />}
                        </div>
                        <p className="text-xs text-muted-foreground mb-3">Set up how you get paid.</p>
                        {!progress.step_payout_added && (
                          <Button size="sm" variant="secondary" disabled={!progress.step_id_approved} className="w-full" onClick={() => router.push(routes.sellerOnboardingAddPayout())}>
                            Add Payout
                          </Button>
                        )}
                     </div>
                   </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">Welcome back, {displayName}! 👋</h1>
            <p className="text-muted-foreground mt-1">Here's an overview of your seller performance.</p>
          </div>
          <Button onClick={() => router.push(routes.sellerListingNew())} className="gap-2 shrink-0">
            <PlusCircle className="w-4 h-4" /> Add New Listing
          </Button>
        </motion.div>

        {showBusinessUpgrade && (
          <Alert className="bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800">
            <AlertCircle className="w-4 h-4 text-purple-600 dark:text-purple-400" />
            <AlertTitle className="text-purple-800 dark:text-purple-300">Business Upgrade Available!</AlertTitle>
            <AlertDescription className="text-purple-700 dark:text-purple-400/90 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <span>You're doing great! Upgrade to a Business Store for higher selling limits and trust badges.</span>
              <Button size="sm" variant="outline" className="shrink-0 bg-transparent" onClick={() => toast.info('Business upgrade flow coming soon')}>
                Upgrade Now
              </Button>
            </AlertDescription>
          </Alert>
        )}
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {unreadCount > 0 && (
            <Alert className="border-blue-200 bg-blue-50/50 dark:border-blue-900/50 dark:bg-blue-900/20">
              <AlertCircle className="w-4 h-4 text-blue-600" />
              <AlertTitle className="text-blue-800 dark:text-blue-300">New Messages</AlertTitle>
              <AlertDescription className="flex items-center justify-between">
                <span>You have {unreadCount} unread messages from customers.</span>
                <Button size="sm" variant="outline" className="h-7 text-xs bg-transparent" onClick={() => router.push(routes.messages())}>View Messages</Button>
              </AlertDescription>
            </Alert>
          )}

          {openDisputes > 0 && (
            <Alert className="border-orange-200 bg-orange-50/50 dark:border-orange-900/50 dark:bg-orange-900/20">
              <AlertCircle className="w-4 h-4 text-orange-600" />
              <AlertTitle className="text-orange-800 dark:text-orange-400">Action Required: Disputes</AlertTitle>
              <AlertDescription className="flex items-center justify-between">
                <span>There are {openDisputes} open disputes that need your response.</span>
                <Button size="sm" variant="outline" className="h-7 text-xs bg-transparent" onClick={() => router.push(`${routes.sellerOrders()}?status=disputed`)}>Review Disputes</Button>
              </AlertDescription>
            </Alert>
          )}
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total Revenue', value: formatTZS(dashboard?.total_revenue ?? 0), icon: DollarSign, color: 'text-green-600', bg: 'bg-green-100' },
            { label: 'Total Orders', value: dashboard?.total_orders ?? 0, icon: ShoppingBag, color: 'text-orange-600', bg: 'bg-orange-100' },
            { label: 'Escrow Balance', value: formatTZS(dashboard?.escrow_balance ?? 0), icon: Shield, color: 'text-teal-600', bg: 'bg-teal-100' },
            { label: 'Pending Payouts', value: formatTZS(dashboard?.pending_payouts ?? 0), icon: Clock, color: 'text-amber-600', bg: 'bg-amber-100' }
          ].map((stat, i) => (
            <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 * i }}>
              <Card className={`border-0 shadow-sm  ${isStateA ? 'opacity-60 grayscale' : 'opacity-100 hover:shadow-md'} transition-all`}>
                <CardContent className="p-4 sm:p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${stat.bg}`}>
                      <stat.icon className={`w-5 h-5 ${stat.color}`} />
                    </div>
                  </div>
                  {isLoading ? <Skeleton className="h-7 w-24 mb-1" /> : <p className="text-xl sm:text-2xl font-bold">{stat.value}</p>}
                  <p className="text-xs text-muted-foreground mt-1">{stat.label}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Active Listings', value: dashboard?.active_listings ?? 0, icon: Package, color: 'text-blue-600', bg: 'bg-blue-100' },
            { label: 'Total Sales', value: dashboard?.total_sales ?? 0, icon: TrendingUp, color: 'text-purple-600', bg: 'bg-purple-100' },
            { label: 'Store Rating', value: `${dashboard?.avg_rating?.toFixed(1) ?? '0.0'} / 5`, icon: BarChart3, color: 'text-amber-500', bg: 'bg-amber-50' },
            { label: 'Total Reviews', value: dashboard?.total_reviews ?? 0, icon: ClipboardList, color: 'text-pink-600', bg: 'bg-pink-100' }
          ].map((stat, i) => (
            <motion.div key={stat.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 + (0.05 * i) }}>
              <Card className={`border-0 shadow-sm  ${isStateA ? 'opacity-60 grayscale' : 'opacity-100 hover:shadow-md'} transition-all`}>
                <CardContent className="p-4 sm:p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${stat.bg}`}>
                      <stat.icon className={`w-5 h-5 ${stat.color}`} />
                    </div>
                  </div>
                  {isLoading ? <Skeleton className="h-7 w-24 mb-1" /> : <p className="text-xl sm:text-2xl font-bold">{stat.value}</p>}
                  <p className="text-xs text-muted-foreground mt-1">{stat.label}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="lg:col-span-2">
            <Card className="border-0 shadow-sm">
              <CardHeader className="pb-3 text-lg flex flex-row items-center gap-2 font-semibold">
                <BarChart3 className="w-5 h-5 text-primary" /> Revenue Overview
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}</div>
                ) : revenueChart.length > 0 && !isStateA ? (
                  <div className="space-y-2.5">
                    {revenueChart.map((item) => (
                      <div key={item.date} className="flex items-center gap-3">
                        <span className="text-xs text-muted-foreground w-20 shrink-0 font-medium">{formatChartDate(item.date)}</span>
                        <div className="flex-1 h-8 bg-muted rounded-lg overflow-hidden relative">
                          <motion.div initial={{ width: 0 }} animate={{ width: `${Math.max((item.revenue / maxRevenue) * 100, 2)}%` }} transition={{ duration: 0.6 }} className="h-full bg-gradient-to-r from-primary to-orange-400 flex items-center justify-end pr-2" />
                          <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-medium text-muted-foreground">{formatTZS(item.revenue)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <TrendingUp className="w-10 h-10 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">{isStateA ? 'Unlock charts by verifying your shop' : 'No revenue data yet.'}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
            <Card className="border-0 shadow-sm h-full">
              <CardHeader className="pb-3"><CardTitle className="text-lg">Quick Actions</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <Button variant="outline" className="w-full justify-start gap-3 h-12" onClick={() => router.push(routes.sellerListingNew())}>
                  <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center shrink-0"><PlusCircle className="w-4 h-4 text-primary" /></div>
                  <div className="text-left"><p className="text-sm font-medium">Add Listing</p><p className="text-xs text-muted-foreground">List a new product</p></div>
                  <ArrowUpRight className="w-4 h-4 ml-auto text-muted-foreground" />
                </Button>
                <Button variant="outline" className="w-full justify-start gap-3 h-12" onClick={() => router.push(routes.sellerOrders())}>
                  <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center shrink-0"><ClipboardList className="w-4 h-4 text-green-600" /></div>
                  <div className="text-left"><p className="text-sm font-medium">View Orders</p><p className="text-xs text-muted-foreground">Manage your orders</p></div>
                  <ArrowUpRight className="w-4 h-4 ml-auto text-muted-foreground" />
                </Button>
                <Button variant="outline" className="w-full justify-start gap-3 h-12" onClick={() => router.push(routes.sellerPayouts())}>
                  <div className="w-8 h-8 bg-amber-100 rounded-lg flex items-center justify-center shrink-0"><Wallet className="w-4 h-4 text-amber-600" /></div>
                  <div className="text-left"><p className="text-sm font-medium">View Payouts</p><p className="text-xs text-muted-foreground">Track your earnings</p></div>
                  <ArrowUpRight className="w-4 h-4 ml-auto text-muted-foreground" />
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        </div>
    </div>
  );
}
