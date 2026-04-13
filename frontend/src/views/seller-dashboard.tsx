'use client';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { routes } from '@/lib/routes';
import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  DollarSign,
  PlusCircle,
  ClipboardList,
  Wallet,
  ArrowUpRight,
  Shield,
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  Package,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
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
  step_first_product?: boolean;
  step_id_approved?: boolean;
  step_payout_added?: boolean;
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

  const isStateA = isProgressLoading
    ? true
    : Boolean(
        progress &&
          (
            !progress.step_first_product ||
            !progress.step_id_approved ||
            !progress.step_payout_added
          ),
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
      rows.push({
        id: `o-${o.id}`,
        text: `${buyerDisplayName(o)} ordered ${firstLineTitle(o)} — ${formatTZS(orderTotalAmount(o))}`,
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
      <AnimatePresence>
        {isStateA && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mb-2"
          >
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
                    <div
                      className={`p-4 rounded-xl border-2 ${progress?.step_first_product ? 'border-green-200 bg-green-50/50' : 'border-orange-200 bg-white dark:bg-black/20'}`}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <h4 className="font-semibold text-sm">1. First Product</h4>
                        {progress?.step_first_product ? (
                          <CheckCircle2 className="w-5 h-5 text-green-500" />
                        ) : (
                          <div className="w-5 h-5 rounded-full border-2 border-orange-300" />
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mb-3">Add a product to your catalog.</p>
                      {!progress?.step_first_product && (
                        <Button
                          size="sm"
                          variant="secondary"
                          className="w-full"
                          onClick={() => router.push(routes.sellerListingNew())}
                        >
                          Publish Product
                        </Button>
                      )}
                    </div>

                    <div
                      className={`p-4 rounded-xl border-2 ${progress?.step_id_approved ? 'border-green-200 bg-green-50/50' : 'border-orange-200 bg-white dark:bg-black/20'}`}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <h4 className="font-semibold text-sm">2. Verify Identity</h4>
                        {progress?.step_id_approved ? (
                          <CheckCircle2 className="w-5 h-5 text-green-500" />
                        ) : (
                          <div className="w-5 h-5 rounded-full border-2 border-orange-300" />
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mb-3">Confirm your identity for trust.</p>
                      {!progress?.step_id_approved ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          className="w-full"
                          onClick={() => router.push(routes.sellerOnboardingVerifyIdentity())}
                        >
                          {progress?.step_id_submitted ? 'Under Review' : 'Verify Identity'}
                        </Button>
                      ) : null}
                    </div>

                    <div
                      className={`p-4 rounded-xl border-2 ${progress?.step_payout_added ? 'border-green-200 bg-green-50/50' : 'border-orange-200 bg-white dark:bg-black/20'}`}
                    >
                      <div className="flex justify-between items-start mb-2">
                        <h4 className="font-semibold text-sm">3. Payout Method</h4>
                        {progress?.step_payout_added ? (
                          <CheckCircle2 className="w-5 h-5 text-green-500" />
                        ) : (
                          <div className="w-5 h-5 rounded-full border-2 border-orange-300" />
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground mb-3">Set up how you get paid.</p>
                      {!progress?.step_payout_added && (
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={!progress?.step_id_approved}
                          className="w-full"
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
        )}
      </AnimatePresence>

      {/* Finance summary — first thing sellers see */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-emerald-200/80 bg-gradient-to-br from-emerald-50/90 to-card dark:from-emerald-950/30 dark:border-emerald-900/50 shadow-md">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-600" />
              In Escrow
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {isLoading ? (
              <Skeleton className="h-9 w-36" />
            ) : (
              <p className="text-2xl sm:text-3xl font-bold tracking-tight">{formatTZS(inEscrow)}</p>
            )}
            <p className="text-xs text-muted-foreground leading-relaxed">
              Amount held until the buyer confirms receipt. Released automatically in {autoDays} days if the buyer
              does not confirm.
            </p>
          </CardContent>
        </Card>

        <Card className="border-sky-200/80 bg-gradient-to-br from-sky-50/90 to-card dark:from-sky-950/25 dark:border-sky-900/50 shadow-md">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Wallet className="w-4 h-4 text-sky-600" />
              Available to Withdraw
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading ? (
              <Skeleton className="h-9 w-36" />
            ) : (
              <p className="text-2xl sm:text-3xl font-bold tracking-tight">{formatTZS(available)}</p>
            )}
            {available <= 0 ? (
              <p className="text-sm text-muted-foreground">Complete orders to unlock funds</p>
            ) : (
              <Button className="w-full gap-2" onClick={() => router.push(routes.sellerWalletWithdraw())}>
                Withdraw Now
                <ArrowUpRight className="w-4 h-4" />
              </Button>
            )}
          </CardContent>
        </Card>

        <Card className="border-amber-200/80 bg-gradient-to-br from-amber-50/80 to-card dark:from-amber-950/20 dark:border-amber-900/50 shadow-md">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-amber-600" />
              This Month&apos;s Earnings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {isLoading ? (
              <Skeleton className="h-9 w-36" />
            ) : (
              <p className="text-2xl sm:text-3xl font-bold tracking-tight">{formatTZS(thisMonth)}</p>
            )}
            {!isLoading && lastMonth > 0 && (
              <p
                className={`text-sm font-medium flex items-center gap-1 ${monthDeltaPct >= 0 ? 'text-emerald-600' : 'text-red-600'}`}
              >
                {monthDeltaPct >= 0 ? (
                  <TrendingUp className="w-4 h-4 shrink-0" />
                ) : (
                  <TrendingDown className="w-4 h-4 shrink-0" />
                )}
                {monthDeltaPct >= 0 ? '+' : ''}
                {monthDeltaPct}% from last month
              </p>
            )}
            {!isLoading && lastMonth <= 0 && thisMonth > 0 && (
              <p className="text-sm font-medium text-emerald-600">Your first earnings this period</p>
            )}
            {!isLoading && lastMonth <= 0 && thisMonth <= 0 && (
              <p className="text-xs text-muted-foreground">Sales you complete this month show here</p>
            )}
          </CardContent>
        </Card>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
      >
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground">Welcome back, {displayName}</h1>
          <p className="text-muted-foreground mt-1">Here is what needs your attention today.</p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <Button variant="outline" className="gap-2" onClick={() => router.push(routes.sellerAnalytics())}>
            Analytics
          </Button>
          <Button onClick={() => router.push(routes.sellerListingNew())} className="gap-2">
            <PlusCircle className="w-4 h-4" /> Add product
          </Button>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-0 shadow-md shadow-black/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <ClipboardList className="w-5 h-5 text-primary" />
              Orders Needing Action
            </CardTitle>
            <CardDescription>New sales, shipments due, or disputes.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </div>
            ) : actionQueue.length === 0 ? (
              <div className="rounded-xl border bg-muted/30 p-8 text-center text-muted-foreground">
                <Package className="w-10 h-10 mx-auto mb-2 opacity-40" />
                <p className="font-medium text-foreground">All caught up! 🎉</p>
                <p className="text-sm mt-1">No orders need your attention right now.</p>
              </div>
            ) : (
              actionQueue.map(({ order, actionLabel, kind }) => (
                <div
                  key={`${order.id}-${actionLabel}`}
                  className="flex flex-col sm:flex-row sm:items-center gap-3 rounded-xl border bg-card p-4"
                >
                  <div className="flex-1 min-w-0 space-y-1">
                    <p className="font-medium text-foreground truncate">{buyerDisplayName(order)}</p>
                    <p className="text-sm text-muted-foreground truncate">{firstLineTitle(order)}</p>
                    {kind === 'payment' && (
                      <p className="text-xs text-blue-800/90 dark:text-blue-200/90">
                        Awaiting buyer payment — ship only after payment clears (no pay on delivery).
                      </p>
                    )}
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span className="font-semibold text-foreground">{formatTZS(orderTotalAmount(order))}</span>
                      <span>·</span>
                      <span>{getRelativeTime(order.created_at)}</span>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    className="shrink-0 w-full sm:w-auto"
                    variant={order.status === 'disputed' ? 'destructive' : 'default'}
                    onClick={() => router.push(routes.sellerOrder(String(order.id)))}
                  >
                    {actionLabel}
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="border-0 shadow-md shadow-black/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Recent Activity</CardTitle>
            <CardDescription>Last updates across your shop.</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : activityItems.length === 0 ? (
              <p className="text-sm text-muted-foreground py-6 text-center">No recent activity yet.</p>
            ) : (
              <ul className="space-y-3">
                {activityItems.map((item) => (
                  <li key={item.id} className="text-sm border-b border-border/60 pb-3 last:border-0 last:pb-0">
                    <Link href={item.href} className="font-medium text-foreground hover:text-primary hover:underline">
                      {item.text}
                    </Link>
                    <p className="text-xs text-muted-foreground mt-1">
                      {item.at ? getRelativeTime(item.at) : ''}
                    </p>
                  </li>
                ))}
              </ul>
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
          <Card className="border-0 shadow-sm">
            <CardHeader className="pb-3 text-lg flex flex-row items-center gap-2 font-semibold">
              Revenue overview
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}</div>
              ) : revenueChart.length > 0 && !isStateA ? (
                <div className="space-y-2.5">
                  {revenueChart.map((item) => (
                    <div key={item.date} className="flex items-center gap-3">
                      <span className="text-xs text-muted-foreground w-20 shrink-0 font-medium">
                        {formatChartDate(item.date)}
                      </span>
                      <div className="flex-1 h-8 bg-muted rounded-lg overflow-hidden relative">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.max((item.revenue / maxRevenue) * 100, 2)}%` }}
                          transition={{ duration: 0.6 }}
                          className="h-full bg-gradient-to-r from-primary to-orange-400 flex items-center justify-end pr-2"
                        />
                        <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-medium text-muted-foreground">
                          {formatTZS(item.revenue)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p className="text-sm">{isStateA ? 'Charts unlock after you verify your shop.' : 'No revenue chart data yet.'}</p>
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
