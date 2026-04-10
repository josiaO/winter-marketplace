'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  DollarSign,
  ShoppingBag,
  Package,
  Clock,
  TrendingUp,
  PlusCircle,
  ClipboardList,
  Wallet,
  ArrowUpRight,
  BarChart3,
  Shield,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, formatDate, getStatusColor, getStatusLabel } from '@/lib/helpers';
import type { Order, SellerStats } from '@/types/api';

export function SellerDashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [dashboard, setDashboard] = useState<SellerStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push(routes.login());
      return;
    }
    if (!user?.is_seller) {
      toast.error('You must be a seller to access the dashboard.');
      router.push(routes.sellerRegister());
      return;
    }

    async function loadDashboard() {
      try {
        const stats = await api.commerce.sellerStats();
        setDashboard(stats);
      } catch {
        toast.error('Failed to load dashboard data.');
      } finally {
        setIsLoading(false);
      }
    }
    loadDashboard();
  }, [isAuthenticated, user, router]);

  if (!isAuthenticated || !user) return null;

  // Helper to get display name
  const displayName = user.first_name || user.last_name
    ? [user.first_name, user.last_name].filter(Boolean).join(' ')
    : user.username;

  const revenueChart = dashboard?.revenue_chart ?? [];
  const maxRevenue = revenueChart.length
    ? Math.max(...revenueChart.map((m) => m.revenue), 1)
    : 1;

  // Format date for chart labels
  const formatChartDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  const stats = [
    {
      label: 'Total Orders',
      value: dashboard?.total_orders ?? 0,
      icon: ShoppingBag,
      color: 'text-orange-600 dark:text-orange-400',
      bg: 'bg-orange-100 dark:bg-orange-900/30',
    },
    {
      label: 'Revenue',
      value: formatTZS(dashboard?.total_revenue ?? 0),
      icon: DollarSign,
      color: 'text-green-600 dark:text-green-400',
      bg: 'bg-green-100 dark:bg-green-900/30',
    },
    {
      label: 'Pending Payouts',
      value: formatTZS(dashboard?.pending_payouts ?? 0),
      icon: Clock,
      color: 'text-amber-600 dark:text-amber-400',
      bg: 'bg-amber-100 dark:bg-amber-900/30',
    },
    {
      label: 'Products Listed',
      value: dashboard?.active_listings ?? 0,
      icon: Package,
      color: 'text-purple-600 dark:text-purple-400',
      bg: 'bg-purple-100 dark:bg-purple-900/30',
    },
    {
      label: 'Escrow Balance',
      value: formatTZS(dashboard?.escrow_balance ?? 0),
      icon: Shield, // Need to ensure Shield is imported
      color: 'text-teal-600 dark:text-teal-400',
      bg: 'bg-teal-100 dark:bg-teal-900/30',
    },
  ];

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Welcome Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
              Welcome back, {displayName}! 👋
            </h1>
            <p className="text-muted-foreground mt-1">
              Here&apos;s an overview of your seller performance.
            </p>
          </div>
          <Button onClick={() => router.push(routes.sellerListingNew())} className="gap-2 shrink-0">
            <PlusCircle className="w-4 h-4" />
            Add New Listing
          </Button>
        </motion.div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {stats.map((stat, index) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * index }}
            >
              <Card className="border-0 shadow-md shadow-black/5 hover:shadow-lg transition-shadow">
                <CardContent className="p-4 sm:p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${stat.bg}`}>
                      <stat.icon className={`w-5 h-5 ${stat.color}`} />
                    </div>
                  </div>
                  {isLoading ? (
                    <Skeleton className="h-7 w-24 mb-1" />
                  ) : (
                    <p className="text-xl sm:text-2xl font-bold text-foreground">
                      {stat.value}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">{stat.label}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Revenue Chart + Quick Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Revenue Chart */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="lg:col-span-2"
          >
            <Card className="border-0 shadow-md shadow-black/5">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-primary" />
                  Revenue Overview
                </CardTitle>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 6 }).map((_, i) => (
                      <Skeleton key={i} className="h-8 w-full" />
                    ))}
                  </div>
                ) : revenueChart.length > 0 ? (
                  <div className="space-y-2.5">
                    {revenueChart.map((item) => (
                      <div key={item.date} className="flex items-center gap-3">
                        <span className="text-xs text-muted-foreground w-20 shrink-0 font-medium">
                          {formatChartDate(item.date)}
                        </span>
                        <div className="flex-1 h-8 bg-muted rounded-lg overflow-hidden relative">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{
                              width: `${Math.max((item.revenue / maxRevenue) * 100, 2)}%`,
                            }}
                            transition={{ duration: 0.6, ease: 'easeOut' }}
                            className="h-full bg-gradient-to-r from-primary to-orange-400 rounded-lg flex items-center justify-end pr-2"
                          >
                            {(item.revenue / maxRevenue) * 100 > 15 && (
                              <span className="text-[10px] font-semibold text-white">
                                {formatTZS(item.revenue)}
                              </span>
                            )}
                          </motion.div>
                          {(item.revenue / maxRevenue) * 100 <= 15 && item.revenue > 0 && (
                            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-medium text-muted-foreground">
                              {formatTZS(item.revenue)}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    <TrendingUp className="w-10 h-10 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">No revenue data yet.</p>
                    <p className="text-xs mt-1">Start selling to see your revenue chart.</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>

          {/* Quick Actions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
          >
            <Card className="border-0 shadow-md shadow-black/5 h-full">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Quick Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button
                  variant="outline"
                  className="w-full justify-start gap-3 h-12"
                  onClick={() => router.push(routes.sellerListingNew())}
                >
                  <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center shrink-0">
                    <PlusCircle className="w-4 h-4 text-primary" />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium">Add Listing</p>
                    <p className="text-xs text-muted-foreground">List a new product</p>
                  </div>
                  <ArrowUpRight className="w-4 h-4 ml-auto text-muted-foreground" />
                </Button>
                <Button
                  variant="outline"
                  className="w-full justify-start gap-3 h-12"
                  onClick={() => router.push(routes.sellerOrders())}
                >
                  <div className="w-8 h-8 bg-green-100 dark:bg-green-900/30 rounded-lg flex items-center justify-center shrink-0">
                    <ClipboardList className="w-4 h-4 text-green-600 dark:text-green-400" />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium">View Orders</p>
                    <p className="text-xs text-muted-foreground">Manage your orders</p>
                  </div>
                  <ArrowUpRight className="w-4 h-4 ml-auto text-muted-foreground" />
                </Button>
                <Button
                  variant="outline"
                  className="w-full justify-start gap-3 h-12"
                  onClick={() => router.push(routes.sellerPayouts())}
                >
                  <div className="w-8 h-8 bg-amber-100 dark:bg-amber-900/30 rounded-lg flex items-center justify-center shrink-0">
                    <Wallet className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium">View Payouts</p>
                    <p className="text-xs text-muted-foreground">Track your earnings</p>
                  </div>
                  <ArrowUpRight className="w-4 h-4 ml-auto text-muted-foreground" />
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* Recent Orders */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <ShoppingBag className="w-5 h-5 text-primary" />
                Recent Orders
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                className="gap-1.5"
                onClick={() => router.push(routes.sellerOrders())}
              >
                View All
                <ArrowUpRight className="w-3.5 h-3.5" />
              </Button>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : dashboard?.recent_orders && dashboard.recent_orders.length > 0 ? (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Order</TableHead>
                        <TableHead>Buyer</TableHead>
                        <TableHead className="hidden sm:table-cell">Items</TableHead>
                        <TableHead>Total</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="hidden md:table-cell">Date</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {dashboard.recent_orders.slice(0, 5).map((order) => (
                        <TableRow
                          key={order.id}
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => router.push(routes.order(String(order.id)))}
                        >
                          <TableCell className="font-medium text-sm">
                            #{order.order_number.slice(-8)}
                          </TableCell>
                          <TableCell className="text-sm">
                            {order.buyer
                              ? [order.buyer.first_name, order.buyer.last_name].filter(Boolean).join(' ') || order.buyer.username
                              : 'Unknown'}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                            {order.items.length} item{order.items.length !== 1 ? 's' : ''}
                          </TableCell>
                          <TableCell className="text-sm font-medium">
                            {formatTZS(order.total)}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="secondary"
                              className={`text-xs ${getStatusColor(order.status)}`}
                            >
                              {getStatusLabel(order.status)}
                            </Badge>
                          </TableCell>
                          <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                            {formatDate(order.created_at)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <ShoppingBag className="w-10 h-10 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No orders yet.</p>
                  <p className="text-xs mt-1">Orders will appear here once customers purchase your products.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
