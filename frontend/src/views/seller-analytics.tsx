'use client';

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { BarChart3, Clock, Package, Users, ChevronLeft } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { api } from '@/lib/api-client';
import { routes } from '@/lib/routes';
import { useAuthStore } from '@/store';
import { canAccessSellerPortal } from '@/lib/auth-roles';
import { useRouter } from 'next/navigation';
import type { Order, Listing, PaginatedResponse } from '@/types/api';
import { formatTZS, commerceOrderItemTitle, commerceOrderItemImage, orderTotalAmount } from '@/lib/helpers';
import { Button } from '@/components/ui/button';
import Link from 'next/link';

function monthStart(): Date {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function inThisMonth(iso: string): boolean {
  const t = new Date(iso).getTime();
  return t >= monthStart().getTime();
}

export function SellerAnalyticsPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [orders, setOrders] = useState<Order[]>([]);
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated || !user || !canAccessSellerPortal(user)) {
      router.push(routes.login());
      return;
    }
    void (async () => {
      try {
        const [o, l] = await Promise.all([
          api.commerce.orders({ role: 'seller', page_size: 200 }),
          api.listings.sellerListings({ page_size: 200 }),
        ]);
        const ord = (o as PaginatedResponse<Order>).results ?? [];
        const lst = (l as { results?: Listing[] }).results ?? [];
        setOrders(ord as Order[]);
        setListings(lst as Listing[]);
      } catch {
        toast.error('Could not load analytics.');
      } finally {
        setLoading(false);
      }
    })();
  }, [isAuthenticated, user, router]);

  const metrics = useMemo(() => {
    const mo = orders.filter((o) => inThisMonth(o.created_at));
    const completed = mo.filter((o) => o.status === 'completed').length;
    const cancelled = mo.filter((o) => o.status === 'cancelled').length;
    const disputed = mo.filter((o) => o.status === 'disputed').length;
    const bad = cancelled + disputed;
    const received = mo.length;
    const completion = received ? Math.round((completed / received) * 100) : 0;
    const totals = mo
      .filter((o) => ['delivered', 'completed'].includes(o.status))
      .reduce((s, o) => s + orderTotalAmount(o), 0);
    const aov = completed ? totals / completed : 0;

    const unitsByListing: Record<number, { qty: number; revenue: number; title: string; image?: string | null }> = {};
    for (const o of mo) {
      if (!['delivered', 'completed'].includes(o.status)) continue;
      for (const it of o.items || []) {
        const lid = typeof it.listing === 'object' && it.listing ? it.listing.id : it.listing_id;
        if (!lid) continue;
        if (!unitsByListing[lid]) {
          const listing = typeof it.listing === 'object' ? it.listing : null;
          unitsByListing[lid] = {
            qty: 0,
            revenue: 0,
            title: commerceOrderItemTitle(it),
            image: commerceOrderItemImage(it),
          };
        }
        const line = Number(it.subtotal ?? it.total ?? 0) || 0;
        unitsByListing[lid].qty += it.quantity || 0;
        unitsByListing[lid].revenue += line;
      }
    }
    const top = Object.entries(unitsByListing)
      .map(([id, v]) => ({ id: Number(id), ...v }))
      .sort((a, b) => b.qty - a.qty)
      .slice(0, 5);

    const buyerIds = new Set<number>();
    const buyerOrderCount: Record<number, number> = {};
    for (const o of mo) {
      if (!o.buyer?.id) continue;
      buyerIds.add(o.buyer.id);
      buyerOrderCount[o.buyer.id] = (buyerOrderCount[o.buyer.id] || 0) + 1;
    }
    const returning = Object.values(buyerOrderCount).filter((c) => c > 1).length;
    const newBuyers = buyerIds.size - returning;
    const returningPct = buyerIds.size ? Math.round((returning / buyerIds.size) * 100) : 0;

    const confirmMs: number[] = [];
    const shipMs: number[] = [];
    for (const o of orders) {
      if (o.confirmed_at && o.created_at) {
        confirmMs.push(new Date(o.confirmed_at).getTime() - new Date(o.created_at).getTime());
      }
      if (o.shipped_at && o.confirmed_at) {
        shipMs.push(new Date(o.shipped_at).getTime() - new Date(o.confirmed_at).getTime());
      }
    }
    const avg = (arr: number[]) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0);
    const avgConfirmH = avg(confirmMs) / 3600000;
    const avgShipH = avg(shipMs) / 3600000;
    const shipOk = avgShipH <= 24;

    const zeroSales = listings.filter((l) => !unitsByListing[l.id]);

    return {
      received,
      completed,
      bad,
      completion,
      aov,
      top,
      newBuyers,
      returning,
      returningPct,
      avgConfirmH,
      avgShipH,
      shipOk,
      zeroSales,
    };
  }, [orders, listings]);

  if (!isAuthenticated || !user) return null;

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
      >
        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            size="icon"
            className="rounded-full shadow-sm bg-white shrink-0"
            onClick={() => router.push(routes.sellerDashboard())}
          >
            <ChevronLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2">
              <BarChart3 className="w-8 h-8 text-primary" />
              Analytics
            </h1>
            <p className="text-muted-foreground mt-1">Numbers that help you decide what to do next.</p>
          </div>
        </div>
        <Button
          variant="outline"
          className="gap-2 shrink-0"
          onClick={() => router.push(routes.sellerDashboard())}
        >
          <BarChart3 className="w-4 h-4 text-primary" />
          Dashboard
        </Button>
      </motion.div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Performance this month</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {[
            { label: 'Orders received', value: metrics.received },
            { label: 'Completed successfully', value: metrics.completed },
            { label: 'Cancelled or disputed', value: metrics.bad },
            { label: 'Completion rate', value: `${metrics.completion}%` },
            { label: 'Average order value', value: formatTZS(metrics.aov) },
          ].map((m) => (
            <Card key={m.label} className="border-0 shadow-md">
              <CardContent className="p-4">
                {loading ? <Skeleton className="h-8 w-20" /> : <p className="text-2xl font-bold">{m.value}</p>}
                <p className="text-xs text-muted-foreground mt-1">{m.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Best selling products (this month)</h2>
        <Card className="border-0 shadow-md">
          <CardContent className="p-4 space-y-3">
            {loading ? (
              <Skeleton className="h-24 w-full" />
            ) : metrics.top.length === 0 ? (
              <p className="text-sm text-muted-foreground">No completed sales yet this month.</p>
            ) : (
              metrics.top.map((row) => (
                <Link
                  key={row.id}
                  href={routes.sellerListingEdit(String(row.id))}
                  className="flex items-center gap-3 rounded-xl border p-3 hover:bg-muted/40"
                >
                  <div className="w-14 h-14 rounded-lg bg-muted overflow-hidden shrink-0">
                    {row.image ? <img src={row.image} alt="" className="w-full h-full object-cover" /> : <Package className="w-6 h-6 m-4 text-muted-foreground" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{row.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {row.qty} sold · {formatTZS(row.revenue)}
                    </p>
                  </div>
                </Link>
              ))
            )}
          </CardContent>
        </Card>
        {!loading && metrics.zeroSales.length > 0 && (
          <Card className="border-dashed">
            <CardHeader>
              <CardTitle className="text-base">Not selling this month</CardTitle>
              <CardDescription>These listings had no completed sales in the current calendar month.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {metrics.zeroSales.slice(0, 6).map((l) => (
                <div key={l.id} className="flex items-center justify-between gap-2 text-sm">
                  <span className="truncate">{l.title}</span>
                  <Link href={routes.sellerListingEdit(String(l.id))} className="text-primary shrink-0 text-xs">
                    Edit
                  </Link>
                </div>
              ))}
              <p className="text-xs text-muted-foreground pt-2">
                Consider lowering the price or improving the photos so buyers choose you over similar listings.
              </p>
            </CardContent>
          </Card>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Users className="w-5 h-5" />
          Buyer loyalty (this month)
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Card className="border-0 shadow-md">
            <CardContent className="p-4">
              {loading ? <Skeleton className="h-8 w-16" /> : <p className="text-2xl font-bold">{metrics.newBuyers}</p>}
              <p className="text-xs text-muted-foreground mt-1">New buyers</p>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-md">
            <CardContent className="p-4">
              {loading ? <Skeleton className="h-8 w-16" /> : <p className="text-2xl font-bold">{metrics.returning}</p>}
              <p className="text-xs text-muted-foreground mt-1">Returning buyers</p>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-md">
            <CardContent className="p-4">
              {loading ? <Skeleton className="h-8 w-16" /> : <p className="text-2xl font-bold">{metrics.returningPct}%</p>}
              <p className="text-xs text-muted-foreground mt-1">Share returning</p>
            </CardContent>
          </Card>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Clock className="w-5 h-5" />
          Response time
        </h2>
        <Card className="border-0 shadow-md">
          <CardContent className="p-4 space-y-3 text-sm">
            {loading ? (
              <Skeleton className="h-20 w-full" />
            ) : (
              <>
                <div className="flex justify-between gap-4">
                  <span className="text-muted-foreground">Order placed → you confirm (avg.)</span>
                  <span className="font-medium">{metrics.avgConfirmH.toFixed(1)} h</span>
                </div>
                <div className="flex justify-between gap-4">
                  <span className="text-muted-foreground">Confirmed → shipped (avg.)</span>
                  <span className={`font-medium ${metrics.shipOk ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {metrics.avgShipH.toFixed(1)} h
                  </span>
                </div>
                <p className="text-xs text-muted-foreground border-t pt-3">
                  Top sellers ship within 24 hours of confirmation.{' '}
                  <span className={metrics.shipOk ? 'text-emerald-600 font-medium' : 'text-amber-600 font-medium'}>
                    {metrics.shipOk ? 'You are on track.' : 'Aim to ship faster to win more repeat buyers.'}
                  </span>
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
