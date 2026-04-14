'use client';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { routes } from '@/lib/routes';
import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bell,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  LayoutDashboard,
  Lightbulb,
  Package,
  PlusCircle,
  Settings,
  Shield,
  ShieldCheck,
  Store,
  User,
  Wallet,
  ArrowUpRight,
  DollarSign,
  AlertTriangle,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import {
  formatTZS,
  getRelativeTime,
  orderTotalAmount,
  commerceOrderItemTitle,
} from '@/lib/helpers';
import type { CommerceSellerStats, Order, PaginatedResponse, SellerStats, Notification } from '@/types/api';

type OnboardingProgressState = {
  step_registration?: boolean;
  step_store_setup?: boolean;
  step_first_product?: boolean;
  step_id_approved?: boolean;
  step_payout_added?: boolean;
  step_id_submitted?: boolean;
  step_business_upgraded?: boolean;
};

type ActionOrder = {
  order: Order;
  kind: 'payment' | 'ship' | 'dispute';
  actionLabel: string;
};

function buyerDisplayName(order: Order): string {
  const b = order.buyer;
  if (!b) return 'Buyer';
  const n = [b.first_name, b.last_name].filter(Boolean).join(' ');
  return n || b.username || 'Buyer';
}

function firstLineTitle(order: Order): string {
  const it = order.items?.[0];
  if (!it) return 'Order';
  return commerceOrderItemTitle(it);
}

export function SellerDashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [commerceStats, setCommerceStats] = useState<CommerceSellerStats | null>(null);
  const [insights, setInsights] = useState<SellerStats | null>(null);
  const [progress, setProgress] = useState<OnboardingProgressState | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isProgressLoading, setIsProgressLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated || !user?.is_seller) return;

    async function loadData() {
      try {
        const [cStats, ins, prog, ordRes, notifRes] = await Promise.all([
          api.commerce.sellerStats() as Promise<CommerceSellerStats>,
          api.insights.sellerStats() as Promise<SellerStats>,
          api.sellers.onboardingProgress(),
          api.commerce.orders({ role: 'seller' }),
          api.communications.notifications({ limit: 15 }).catch(() => ({ results: [] as Notification[] })),
        ]);
        setCommerceStats(cStats);
        setInsights(ins);
        setProgress(prog as OnboardingProgressState);
        const items =
          (ordRes as PaginatedResponse<Order>).results ??
          (Array.isArray(ordRes) ? ordRes : []);
        setOrders(items as Order[]);
        setNotifications((notifRes as PaginatedResponse<Notification>).results ?? []);
      } catch {
        toast.error('Failed to load dashboard data.');
      } finally {
        setIsLoading(false);
        setIsProgressLoading(false);
      }
    }
    loadData();
  }, [isAuthenticated, user]);

  if (!isAuthenticated || !user) return null;

  const displayName = user.first_name || user.last_name
    ? [user.first_name, user.last_name].filter(Boolean).join(' ')
    : user.username;

  const isOnboardingIncomplete = isProgressLoading
    ? true
    : Boolean(
        progress &&
          (
            !progress.step_store_setup ||
            !progress.step_first_product ||
            !progress.step_id_approved ||
            !progress.step_payout_added
          ),
      );
      
  const showBusinessUpgrade = Boolean(
    progress?.step_id_approved && !progress?.step_business_upgraded
  );

  const autoDays = commerceStats?.policy?.auto_confirm_receipt_days ?? 7;
  const inEscrow = commerceStats?.escrow?.held ?? 0;
  const available = Math.max(0, commerceStats?.escrow?.available_for_withdrawal ?? 0);
  const thisMonth = commerceStats?.revenue?.this_month ?? 0;
  const lastMonth = commerceStats?.revenue?.last_month ?? 0;
  const monthDeltaPct =
    lastMonth > 0 ? Math.round(((thisMonth - lastMonth) / lastMonth) * 100) : thisMonth > 0 ? 100 : 0;

  const actionQueue = useMemo((): ActionOrder[] => {
    const out: ActionOrder[] = [];
    for (const o of orders) {
      if (o.status === 'pending') {
        out.push({
          order: o,
          kind: 'payment',
          actionLabel: 'View order',
        });
      } else if (o.status === 'confirmed' || o.status === 'processing') {
        out.push({ order: o, kind: 'ship', actionLabel: 'Mark shipped' });
      } else if (o.status === 'disputed') {
        out.push({ order: o, kind: 'dispute', actionLabel: 'Respond to dispute' });
      }
    }
    return out.slice(0, 12);
  }, [orders]);

  const activityItems = useMemo(() => {
    const rows: {
      id: string;
      text: string;
      at: string;
      href: string;
    }[] = [];

    for (const n of notifications.slice(0, 10)) {
      rows.push({
        id: `n-${n.id}`,
        text: n.body || n.title || 'Update',
        at: n.created_at || '',
        href: routes.notifications(),
      });
    }

    const sortedOrders = [...orders].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
    for (const o of sortedOrders.slice(0, 5)) {
      if (rows.length >= 10) break;
      const bname = buyerDisplayName(o);
      const title = firstLineTitle(o);
      const amt = formatTZS(orderTotalAmount(o));
      let text = `${bname} ordered ${title} — ${amt}`;
      
      if (o.status === 'confirmed' || o.status === 'processing') {
        text = `${bname} paid ${amt} for ${title}`;
      } else if (o.status === 'shipped') {
        text = `You shipped ${title} to ${bname}`;
      } else if (o.status === 'completed') {
        text = `Order for ${title} completed. Funds released!`;
      } else if (o.status === 'disputed') {
        text = `⚠️ Dispute opened for ${title} by ${bname}`;
      }

      rows.push({
        id: `o-${o.id}`,
        text,
        at: o.created_at,
        href: routes.sellerOrder(String(o.id)),
      });
    }

    return rows
      .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
      .slice(0, 10);
  }, [notifications, orders]);

  const revenueChart = insights?.revenue_chart ?? [];
  const maxRevenue = revenueChart.length ? Math.max(...revenueChart.map((m) => m.revenue), 1) : 1;
  const formatChartDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-6">
      <AnimatePresence mode="wait">
        {isOnboardingIncomplete ? (
          <motion.div
            key="onboarding"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="mb-8"
          >
            <Card className="border-0 shadow-2xl bg-gradient-to-br from-indigo-50 to-white dark:from-indigo-950/20 dark:to-zinc-900 border-l-4 border-l-primary overflow-hidden">
              <CardHeader className="pb-4">
                <div className="flex items-center justify-between">
                    <div className="space-y-1">
                        <CardTitle className="text-2xl font-black text-indigo-900 dark:text-indigo-300 flex items-center gap-3">
                            <Shield className="w-8 h-8 text-primary" />
                            Secure Your Store
                        </CardTitle>
                        <CardDescription className="text-indigo-700/80 dark:text-indigo-300/80 text-base font-medium">
                            Complete these missions to start selling and receiving payouts.
                        </CardDescription>
                    </div>
                    <div className="hidden sm:block">
                        <Badge className="bg-primary/20 text-primary border-primary/20 px-3 py-1 font-bold">
                            PHASE 1: IDENTITY
                        </Badge>
                    </div>
                </div>
              </CardHeader>
              <CardContent>
                {isProgressLoading ? (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                    <Skeleton className="h-32 rounded-3xl" />
                    <Skeleton className="h-32 rounded-3xl" />
                    <Skeleton className="h-32 rounded-3xl" />
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div
                      className={`group p-6 rounded-3xl border-2 transition-all ${progress?.step_store_setup ? 'border-emerald-200 bg-emerald-50/50' : 'border-indigo-100 bg-white hover:border-primary/30'}`}
                    >
                      <div className="flex justify-between items-start mb-3">
                        <div className="w-10 h-10 rounded-2xl bg-indigo-50 flex items-center justify-center">
                            <Store className={`w-5 h-5 ${progress?.step_store_setup ? 'text-emerald-600' : 'text-primary'}`} />
                        </div>
                        {progress?.step_store_setup ? (
                          <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                        ) : (
                          <div className="w-6 h-6 rounded-full border-2 border-primary/20" />
                        )}
                      </div>
                      <h4 className="font-bold text-gray-900 mb-1">1. Store Basics</h4>
                      <p className="text-xs text-muted-foreground mb-4 font-medium leading-relaxed">Name and category for your shop.</p>
                      {!progress?.step_store_setup && (
                        <Button
                          size="sm"
                          className="w-full rounded-xl font-bold transition-all group-hover:shadow-lg shadow-primary/20"
                          onClick={() => router.push(routes.sellerOnboardingStoreSetup())}
                        >
                          Setup Shop
                        </Button>
                      )}
                    </div>

                    <div
                      className={`group p-6 rounded-3xl border-2 transition-all ${progress?.step_first_product ? 'border-emerald-200 bg-emerald-50/50' : 'border-indigo-100 bg-white hover:border-primary/30'}`}
                    >
                      <div className="flex justify-between items-start mb-3">
                        <div className="w-10 h-10 rounded-2xl bg-indigo-50 flex items-center justify-center">
                            <Package className={`w-5 h-5 ${progress?.step_first_product ? 'text-emerald-600' : 'text-primary'}`} />
                        </div>
                        {progress?.step_first_product ? (
                          <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                        ) : (
                          <div className="w-6 h-6 rounded-full border-2 border-primary/20" />
                        )}
                      </div>
                      <h4 className="font-bold text-gray-900 mb-1">2. Add Product</h4>
                      <p className="text-xs text-muted-foreground mb-4 font-medium leading-relaxed">
                        Your listings will show as <span className="text-amber-600 font-bold italic">Unverified</span> until you complete Step 3.
                      </p>
                      {!progress?.step_first_product && (
                        <Button
                          size="sm"
                          disabled={!progress?.step_store_setup}
                          className="w-full rounded-xl font-bold transition-all group-hover:shadow-lg shadow-primary/20"
                          onClick={() => router.push(routes.sellerListingNew())}
                        >
                          List Now
                        </Button>
                      )}
                    </div>

                    <div
                      className={`group p-6 rounded-3xl border-2 transition-all ${progress?.step_id_approved ? 'border-emerald-200 bg-emerald-50/50' : 'border-indigo-100 bg-white hover:border-primary/30'}`}
                    >
                        <div className="flex justify-between items-start mb-3">
                            <div className="w-10 h-10 rounded-2xl bg-indigo-50 flex items-center justify-center">
                                <User className={`w-5 h-5 ${progress?.step_id_approved ? 'text-emerald-600' : 'text-primary'}`} />
                            </div>
                            {progress?.step_id_approved ? (
                            <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                            ) : (
                            <div className="w-6 h-6 rounded-full border-2 border-primary/20" />
                            )}
                        </div>
                      <h4 className="font-bold text-gray-900 mb-1">3. Verify Identity</h4>
                      <p className="text-xs text-muted-foreground mb-4 font-medium leading-relaxed">Required for trust and payout safety.</p>
                      {!progress?.step_id_approved ? (
                        <Button
                          size="sm"
                          disabled={!progress?.step_first_product}
                          className={`w-full rounded-xl font-bold transition-all ${progress?.step_id_submitted ? 'bg-amber-100 text-amber-700 hover:bg-amber-200' : 'group-hover:shadow-lg shadow-primary/20'}`}
                          onClick={() => router.push(routes.sellerOnboardingVerifyIdentity())}
                        >
                          {progress?.step_id_submitted ? 'Under Review' : 'Verify Identity'}
                        </Button>
                      ) : (
                          <p className="text-[10px] font-black text-emerald-600 uppercase tracking-widest text-center mt-2">Verified Seller</p>
                      )}
                    </div>

                    <div
                      className={`group p-6 rounded-3xl border-2 transition-all ${progress?.step_payout_added ? 'border-emerald-200 bg-emerald-50/50' : 'border-indigo-100 bg-white hover:border-primary/30'}`}
                    >
                        <div className="flex justify-between items-start mb-3">
                            <div className="w-10 h-10 rounded-2xl bg-indigo-50 flex items-center justify-center">
                                <Wallet className={`w-5 h-5 ${progress?.step_payout_added ? 'text-emerald-600' : 'text-primary'}`} />
                            </div>
                            {progress?.step_payout_added ? (
                            <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                            ) : (
                            <div className="w-6 h-6 rounded-full border-2 border-primary/20" />
                            )}
                        </div>
                      <h4 className="font-bold text-gray-900 mb-1">4. Payout Method</h4>
                      <p className="text-xs text-muted-foreground mb-4 font-medium leading-relaxed">Set up your bank or mobile wallet.</p>
                      {!progress?.step_payout_added && (
                        <Button
                          size="sm"
                          disabled={!progress?.step_id_approved}
                          className="w-full rounded-xl font-bold transition-all group-hover:shadow-lg shadow-primary/20"
                          onClick={() => router.push(routes.sellerOnboardingAddPayout())}
                        >
                          Add Payout
                        </Button>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        ) : showBusinessUpgrade ? (
            <motion.div
                key="business-upgrade"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="mb-8"
            >
                <Card className="border-0 shadow-2xl bg-gradient-to-r from-primary to-indigo-600 overflow-hidden relative group">
                    <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-20" />
                    <div className="absolute -right-20 -top-20 w-64 h-64 bg-white/10 blur-3xl rounded-full group-hover:scale-110 transition-transform duration-700" />
                    
                    <CardContent className="p-8 relative">
                        <div className="flex flex-col md:flex-row items-center justify-between gap-8">
                            <div className="space-y-4 max-w-2xl text-center md:text-left">
                                <Badge className="bg-white/20 text-white border-white/30 px-3 py-1 font-bold text-xs">
                                    AVAILABLE GROWTH OPPORTUNITY
                                </Badge>
                                <h3 className="text-3xl font-black text-white leading-none">Upgrade to Business Seller</h3>
                                <p className="text-primary-foreground/90 font-medium text-lg">
                                    Unlock 500+ product listings, unlimited daily payouts, and the "Verified Business" trust badge.
                                </p>
                                <div className="flex flex-wrap justify-center md:justify-start gap-4 pt-2">
                                    <div className="bg-white/10 backdrop-blur-md border border-white/20 px-4 py-2 rounded-2xl flex items-center gap-2 text-white">
                                        <ArrowUpRight className="w-4 h-4" />
                                        <span className="text-xs font-bold uppercase">Higher Visibility</span>
                                    </div>
                                    <div className="bg-white/10 backdrop-blur-md border border-white/20 px-4 py-2 rounded-2xl flex items-center gap-2 text-white">
                                        <Shield className="w-4 h-4" />
                                        <span className="text-xs font-bold uppercase">Business Trust</span>
                                    </div>
                                </div>
                            </div>
                            <Button 
                                size="lg" 
                                onClick={() => router.push(routes.sellerOnboardingVerifyBusiness())}
                                className="bg-white text-primary hover:bg-slate-50 h-16 px-8 rounded-2xl font-black text-xl shadow-2xl shadow-black/20 group/btn transition-all hover:scale-105"
                            >
                                Start Upgrade
                                <PlusCircle className="ml-3 w-6 h-6 group-hover/btn:rotate-90 transition-transform" />
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </motion.div>
        ) : null}
      </AnimatePresence>

      {/* Finance summary — first thing sellers see */}
      {/* Finance summary — first thing sellers see */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="relative overflow-hidden border-0 bg-white/50 dark:bg-zinc-900/50 backdrop-blur-xl shadow-xl shadow-emerald-500/5 ring-1 ring-emerald-500/10 dark:ring-emerald-400/20 transition-all hover:ring-emerald-500/30">
          <div className="absolute top-0 right-0 -mr-8 -mt-8 w-32 h-32 bg-emerald-500/10 blur-3xl rounded-full" />
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-emerald-800 dark:text-emerald-300">
              <Shield className="w-4 h-4" />
              In Escrow
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {isLoading ? (
              <Skeleton className="h-9 w-36" />
            ) : (
              <p className="text-2xl sm:text-3xl font-bold tracking-tight text-emerald-950 dark:text-emerald-50">{formatTZS(inEscrow)}</p>
            )}
            <p className="text-[11px] text-emerald-800/70 dark:text-emerald-400/60 leading-relaxed font-medium">
              Released automatically in {autoDays} days if the buyer does not confirm first.
            </p>
          </CardContent>
        </Card>

        <Card className="relative overflow-hidden border-0 bg-white/50 dark:bg-zinc-900/50 backdrop-blur-xl shadow-xl shadow-sky-500/5 ring-1 ring-sky-500/10 dark:ring-sky-400/20 transition-all hover:ring-sky-500/30">
          <div className="absolute top-0 right-0 -mr-8 -mt-8 w-32 h-32 bg-sky-500/10 blur-3xl rounded-full" />
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-sky-800 dark:text-sky-300">
              <Wallet className="w-4 h-4" />
              Available to Withdraw
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading ? (
              <Skeleton className="h-9 w-36" />
            ) : (
              <p className="text-2xl sm:text-3xl font-bold tracking-tight text-sky-950 dark:text-sky-50">{formatTZS(available)}</p>
            )}
            {available <= 0 ? (
              <p className="text-xs font-medium text-sky-800/60 dark:text-sky-400/60">Complete orders to unlock funds</p>
            ) : (
              <Button className="w-full gap-2 bg-sky-600 hover:bg-sky-700 text-white border-0 shadow-lg shadow-sky-500/20" onClick={() => router.push(routes.sellerWalletWithdraw())}>
                Withdraw Now
                <ArrowUpRight className="w-4 h-4" />
              </Button>
            )}
          </CardContent>
        </Card>

        <Card className="relative overflow-hidden border-0 bg-white/50 dark:bg-zinc-900/50 backdrop-blur-xl shadow-xl shadow-amber-500/5 ring-1 ring-amber-500/10 dark:ring-amber-400/20 transition-all hover:ring-amber-500/30">
          <div className="absolute top-0 right-0 -mr-8 -mt-8 w-32 h-32 bg-amber-500/10 blur-3xl rounded-full" />
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-amber-800 dark:text-amber-300">
              <DollarSign className="w-4 h-4" />
              This Month&apos;s Earnings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {isLoading ? (
              <Skeleton className="h-9 w-36" />
            ) : (
              <p className="text-2xl sm:text-3xl font-bold tracking-tight text-amber-950 dark:text-amber-50">{formatTZS(thisMonth)}</p>
            )}
            {!isLoading && lastMonth > 0 && (
              <div
                className={`text-xs font-bold flex items-center gap-1.5 px-2 py-1 rounded-full w-fit ${monthDeltaPct >= 0 ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-400' : 'bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-400'}`}
              >
                {monthDeltaPct >= 0 ? (
                  <TrendingUp className="w-3.5 h-3.5" />
                ) : (
                  <TrendingDown className="w-3.5 h-3.5" />
                )}
                {monthDeltaPct >= 0 ? '+' : ''}
                {monthDeltaPct}%
                <span className="font-normal opacity-70">this month</span>
              </div>
            )}
            {!isLoading && thisMonth === 0 && (
              <div className="pt-1 space-y-2">
                <p className="text-[11px] font-bold text-amber-800/70 dark:text-amber-400/70 italic">
                  Hujauza mwezi huu (No sales yet this month)
                </p>
                <div className="flex items-start gap-2 p-2 rounded-lg bg-amber-100/50 dark:bg-amber-500/10 border border-amber-200/50 dark:border-amber-500/20">
                  <Lightbulb className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                  <p className="text-[10px] leading-tight font-medium text-amber-900/80 dark:text-amber-300/80">
                    Pro tip: Clear photos and competitive prices attract 3x more buyers!
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Header with Trust Level */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col lg:flex-row lg:items-center justify-between gap-6"
      >
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground tracking-tight">Welcome back, {displayName}</h1>
            {progress?.store_is_active ? 
              <Badge className="bg-emerald-500 hover:bg-emerald-600 font-bold px-2 py-0.5 text-[10px] uppercase tracking-wider">Active Shop</Badge> : 
              <Badge variant="secondary" className="font-bold px-2 py-0.5 text-[10px] uppercase tracking-wider">Setup Mode</Badge>
            }
          </div>
          <p className="text-muted-foreground font-medium">Here is what needs your attention today.</p>
        </div>

        {/* Global Trust Score Indicator */}
        <div className="flex items-center gap-4 bg-white/50 dark:bg-zinc-900/50 backdrop-blur-md border rounded-2xl p-4 shadow-sm min-w-[320px] ring-1 ring-black/5">
           <div className="relative w-14 h-14 flex items-center justify-center">
              <svg className="w-full h-full transform -rotate-90">
                <circle
                  cx="28"
                  cy="28"
                  r="24"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="transparent"
                  className="text-muted/20"
                />
                <circle
                  cx="28"
                  cy="28"
                  r="24"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="transparent"
                  strokeDasharray={150.8}
                  strokeDashoffset={150.8 * (1 - (progress?.completion_percentage || 0) / 100)}
                  className="text-primary transition-all duration-1000 ease-out"
                />
              </svg>
              <span className="absolute text-xs font-black">{progress?.completion_percentage || 0}%</span>
           </div>
           <div className="flex-1">
              <div className="flex items-center justify-between">
                <p className="text-[10px] font-black uppercase tracking-widest text-muted-foreground">Verification Score</p>
                <Badge variant="outline" className="text-[9px] h-4 font-black border-primary/20 text-primary">
                    {progress?.completion_percentage && progress.completion_percentage < 50 ? 'Basic' : 
                     progress?.completion_percentage && progress.completion_percentage < 80 ? 'Trusted' : 'Pro'}
                </Badge>
              </div>
              <p className="text-sm font-bold mt-0.5">
                {progress?.completion_percentage && progress.completion_percentage < 50 ? 'Limited Trust' : 
                 progress?.completion_percentage && progress.completion_percentage < 80 ? 'Verified Seller' : 'Elite Merchant'}
              </p>
              <div className="mt-1.5 flex items-center gap-1">
                 <div className="w-full bg-muted h-1 rounded-full overflow-hidden">
                    <div 
                      className="bg-primary h-full transition-all duration-1000" 
                      style={{ width: `${progress?.completion_percentage || 0}%` }}
                    />
                 </div>
              </div>
           </div>
        </div>
      </motion.div>

      {/* Motivation Banner - Dynamic Nudge */}
      {progress && progress.completion_percentage < 100 && (
         <motion.div 
           initial={{ opacity: 0, scale: 0.98 }}
           animate={{ opacity: 1, scale: 1 }}
           className="bg-primary/5 border border-primary/10 rounded-2xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4"
         >
            <div className="flex items-center gap-4">
               <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center text-primary shadow-inner">
                  <ShieldCheck className="w-6 h-6" />
               </div>
               <div>
                  <p className="font-bold text-sm">Boost your buyer trust level</p>
                  <p className="text-xs text-muted-foreground font-medium mt-0.5">
                    {progress.completion_percentage < 50 
                      ? `Reach 50% trust to remove the 'Unverified' badge and build buyer confidence.`
                      : "Upgrade to a Business Seller in settings to reach 100% and unlock unlimited payouts."
                    }
                  </p>
               </div>
            </div>
            <div className="flex items-center gap-3 w-full sm:w-auto">
                <Button size="sm" variant="default" className="flex-1 sm:flex-none font-bold rounded-xl shadow-lg shadow-primary/20" onClick={() => {
                    if (!progress.step_id_approved) {
                        router.push(routes.sellerVerification());
                    } else {
                        router.push(routes.sellerSettings());
                    }
                }}>
                   {progress.step_id_approved ? 'Upgrade to Pro' : 'Increase Trust Score'}
                </Button>
            </div>
         </motion.div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 border-0 bg-white/40 dark:bg-zinc-900/40 backdrop-blur-sm shadow-xl shadow-black/[0.03] ring-1 ring-black/5 dark:ring-white/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2.5 font-bold">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                <ClipboardList className="w-5 h-5 text-primary" />
              </div>
              Orders Needing Action
            </CardTitle>
            <CardDescription className="font-medium">New sales, shipments due, or disputes.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-20 w-full rounded-2xl" />
                <Skeleton className="h-20 w-full rounded-2xl" />
              </div>
            ) : actionQueue.length === 0 ? (
              <div className="py-12 text-center">
                <div className="w-16 h-16 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-4">
                  <Package className="w-8 h-8 text-muted-foreground/40" />
                </div>
                <p className="font-bold text-lg">All caught up! 🎉</p>
                <p className="text-sm text-muted-foreground font-medium">No orders need your attention right now.</p>
              </div>
            ) : (
              actionQueue.map(({ order, actionLabel, kind }) => (
                <motion.div
                  key={`${order.id}-${actionLabel}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex flex-col sm:flex-row sm:items-center gap-4 rounded-2xl border bg-white/50 dark:bg-black/20 p-5 transition-all hover:shadow-md hover:ring-2 hover:ring-primary/10"
                >
                  <div className="flex-1 min-w-0 space-y-1.5">
                    <div className="flex items-center gap-2">
                       <span className="font-bold text-foreground text-base">{buyerDisplayName(order)}</span>
                       <span className="text-xs px-2 py-0.5 rounded-full bg-muted font-bold text-muted-foreground">
                         #{String(order.id).slice(-4)}
                       </span>
                    </div>
                    <p className="text-sm text-muted-foreground font-semibold truncate italic">"{firstLineTitle(order)}"</p>
                    {kind === 'payment' && (
                      <div className="flex items-center gap-1.5 text-xs text-blue-600 dark:text-blue-400 font-bold bg-blue-50 dark:bg-blue-500/10 px-2 py-1 rounded-md w-fit">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        Wait for payment
                      </div>
                    )}
                    {kind === 'dispute' && (
                      <div className="flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400 font-bold bg-red-50 dark:bg-red-500/10 px-2 py-1 rounded-md w-fit">
                        <Shield className="w-3.5 h-3.5" />
                        Response needed
                      </div>
                    )}
                    <div className="flex items-center gap-3 text-xs text-muted-foreground font-bold pt-1">
                      <span className="text-foreground">{formatTZS(orderTotalAmount(order))}</span>
                      <span className="opacity-30">•</span>
                      <span>{getRelativeTime(order.created_at)}</span>
                    </div>
                  </div>
                  <Button
                    size="lg"
                    className={`shrink-0 w-full sm:w-auto font-bold rounded-xl shadow-lg transition-all ${order.status === 'disputed' ? 'bg-red-600 hover:bg-red-700 shadow-red-500/20' : 'shadow-primary/20'}`}
                    onClick={() => router.push(routes.sellerOrder(String(order.id)))}
                  >
                    {actionLabel}
                  </Button>
                </motion.div>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-1 border-0 bg-white/40 dark:bg-zinc-900/40 backdrop-blur-sm shadow-xl shadow-black/[0.03] ring-1 ring-black/5 dark:ring-white/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg font-bold">Activity Log</CardTitle>
            <CardDescription className="font-medium">Last 10 updates.</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-10 w-full rounded-lg" />
                <Skeleton className="h-10 w-full rounded-lg" />
                <Skeleton className="h-10 w-full rounded-lg" />
              </div>
            ) : activityItems.length === 0 ? (
              <div className="py-8 text-center text-muted-foreground font-medium">No recent activity yet.</div>
            ) : (
              <div className="relative pl-4 space-y-6 before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-[2px] before:bg-muted/80">
                {activityItems.map((item) => (
                  <div key={item.id} className="relative">
                    <div className="absolute -left-[21px] top-1 w-[12px] h-[12px] rounded-full bg-primary border-[3px] border-white dark:border-zinc-900 shadow-sm" />
                    <Link href={item.href} className="group block">
                      <p className="text-sm font-bold text-foreground/80 group-hover:text-primary transition-colors leading-snug">
                        {item.text}
                      </p>
                      <p className="text-[10px] font-bold text-muted-foreground mt-1 uppercase tracking-wider opacity-60">
                        {item.at ? getRelativeTime(item.at) : 'recently'}
                      </p>
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="lg:col-span-2"
        >
          <Card className="border-0 shadow-sm overflow-hidden h-full">
            <CardHeader className="pb-3 border-b bg-gray-50/50">
              <div className="flex items-center justify-between">
                <div>
                   <CardTitle className="text-lg font-black flex items-center gap-2 uppercase tracking-tighter">
                    <TrendingUp className="w-5 h-5 text-primary" />
                    Trust & Revenue Analysis
                   </CardTitle>
                   <CardDescription className="font-bold">Growth milestones and marketplace visibility.</CardDescription>
                </div>
                {!progress?.step_business_upgraded && progress?.step_id_approved && (
                    <div className="text-right">
                        <p className="text-[10px] font-black text-gray-400 uppercase">Limit</p>
                        <p className="text-sm font-black text-primary">10 Orders</p>
                    </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              {isLoading ? (
                <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}</div>
              ) : revenueChart.length > 0 && !isOnboardingIncomplete ? (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-3">
                         <div className="flex justify-between items-end">
                            <span className="text-xs font-black uppercase text-gray-500 tracking-widest">Store Trust Level</span>
                            <span className="text-sm font-black text-primary">{progress?.step_business_upgraded ? 'FULLY VERIFIED' : 'IDENTITY ONLY'}</span>
                         </div>
                         <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden">
                            <motion.div 
                                initial={{ width: 0 }}
                                animate={{ width: progress?.step_business_upgraded ? '100%' : '50%' }}
                                className={`h-full ring-1 ring-inset ${progress?.step_business_upgraded ? 'bg-emerald-500 ring-emerald-600' : 'bg-primary ring-primary/50'}`} 
                            />
                         </div>
                         <p className="text-[10px] font-medium text-muted-foreground leading-tight italic">
                            {progress?.step_business_upgraded 
                                ? "Your store has top-tier visibility and no payout thresholds." 
                                : "Upgrade to Business to remove the 10-order threshold."}
                         </p>
                      </div>

                      <div className="space-y-4">
                        {revenueChart.slice(-3).map((item) => (
                            <div key={item.date} className="flex items-center gap-3">
                            <span className="text-xs text-muted-foreground w-20 shrink-0 font-bold uppercase tracking-tighter">
                                {formatChartDate(item.date)}
                            </span>
                            <div className="flex-1 h-8 bg-slate-50 border rounded-xl overflow-hidden relative group">
                                <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${Math.max((item.revenue / maxRevenue) * 100, 2)}%` }}
                                transition={{ duration: 0.6 }}
                                className="h-full bg-gradient-to-r from-primary/80 to-primary flex items-center justify-end pr-2 group-hover:from-primary transition-all shadow-inner"
                                />
                                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-black text-gray-900">
                                {formatTZS(item.revenue)}
                                </span>
                            </div>
                            </div>
                        ))}
                      </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 bg-gray-50/50 rounded-3xl border border-dashed border-gray-200">
                  <Package className="w-12 h-12 mx-auto mb-3 opacity-10" />
                  <p className="text-sm font-bold text-gray-500 px-6">
                    {isOnboardingIncomplete 
                        ? 'Unlock trust scores and revenue charts by completing your identity verification.' 
                        : 'No sales data recorded for the last 6 months.'}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
          <Card className="border-0 shadow-sm h-full">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Quick links</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button variant="outline" className="w-full justify-start gap-3 h-12" onClick={() => router.push(routes.sellerOrders())}>
                <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center shrink-0">
                  <ClipboardList className="w-4 h-4 text-green-600" />
                </div>
                <div className="text-left">
                  <p className="text-sm font-medium">Orders</p>
                  <p className="text-xs text-muted-foreground">Work queue</p>
                </div>
                <ArrowUpRight className="w-4 h-4 ml-auto text-muted-foreground" />
              </Button>
              <Button variant="outline" className="w-full justify-start gap-3 h-12" onClick={() => router.push(routes.sellerWallet())}>
                <div className="w-8 h-8 bg-amber-100 rounded-lg flex items-center justify-center shrink-0">
                  <Wallet className="w-4 h-4 text-amber-600" />
                </div>
                <div className="text-left">
                  <p className="text-sm font-medium">Wallet</p>
                  <p className="text-xs text-muted-foreground">Withdrawals</p>
                </div>
                <ArrowUpRight className="w-4 h-4 ml-auto text-muted-foreground" />
              </Button>
              <Button variant="outline" className="w-full justify-start gap-3 h-12" onClick={() => router.push(routes.sellerReviews())}>
                <div className="w-8 h-8 bg-pink-100 rounded-lg flex items-center justify-center shrink-0">
                  <span className="text-sm">★</span>
                </div>
                <div className="text-left">
                  <p className="text-sm font-medium">Reviews</p>
                  <p className="text-xs text-muted-foreground">Buyer feedback</p>
                </div>
                <ArrowUpRight className="w-4 h-4 ml-auto text-muted-foreground" />
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
