'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  BarChart3,
  DollarSign,
  TrendingUp,
  Users,
  ShoppingCart,
  ArrowUpRight,
  Shield,
  Percent,
  Activity,
  Crown,
  Star,
  Wallet,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
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
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS } from '@/lib/helpers';
import type { PlatformMetrics } from '@/types/api';

const CHART_COLORS = [
  '#10b981',
  '#14b8a6',
  '#0d9488',
  '#0f766e',
  '#115e59',
  '#047857',
  '#065f46',
  '#134e4a',
  '#064e3b',
  '#022c22',
];

const CHART_TOOLTIP_STYLE = {
  backgroundColor: 'hsl(var(--background))',
  border: '1px solid hsl(var(--border))',
  borderRadius: '8px',
  fontSize: '12px',
};

export function AdminAnalyticsPage() {
  const { navigate } = useUIStore();
  const { user, isAuthenticated } = useAuthStore();
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      navigate({ view: 'home' });
      return;
    }

    async function loadMetrics() {
      try {
        const data = await api.insights.platformMetrics();
        setMetrics(data);
      } catch {
        toast.error('Failed to load platform metrics.');
      } finally {
        setIsLoading(false);
      }
    }
    loadMetrics();
  }, [isAuthenticated, user, navigate]);

  if (!isAuthenticated || !user || user.role !== 'admin') return null;

  // KPI metric cards
  const kpiCards = [
    {
      label: 'Gross Merchandise Value',
      value: metrics ? formatTZS(metrics.total_gmv) : '—',
      icon: DollarSign,
      color: 'text-emerald-600 dark:text-emerald-400',
      bg: 'bg-emerald-100 dark:bg-emerald-900/30',
      span: 'sm:col-span-1',
    },
    {
      label: 'Total Commission',
      value: metrics ? formatTZS(metrics.total_commission) : '—',
      icon: TrendingUp,
      color: 'text-teal-600 dark:text-teal-400',
      bg: 'bg-teal-100 dark:bg-teal-900/30',
      span: 'sm:col-span-1',
    },
    {
      label: 'Escrow Held',
      value: metrics ? formatTZS(metrics.total_escrow_held) : '—',
      icon: Shield,
      color: 'text-amber-600 dark:text-amber-400',
      bg: 'bg-amber-100 dark:bg-amber-900/30',
      span: 'sm:col-span-1',
    },
    {
      label: 'Payouts Released',
      value: metrics ? formatTZS(metrics.total_payouts_released) : '—',
      icon: Wallet,
      color: 'text-green-600 dark:text-green-400',
      bg: 'bg-green-100 dark:bg-green-900/30',
      span: 'sm:col-span-1',
    },
    {
      label: 'Active Users (30d)',
      value: metrics?.active_users_30d ?? 0,
      icon: Users,
      color: 'text-blue-600 dark:text-blue-400',
      bg: 'bg-blue-100 dark:bg-blue-900/30',
      span: 'sm:col-span-1',
    },
    {
      label: 'Conversion Rate',
      value: metrics ? `${metrics.conversion_rate}%` : '—',
      icon: Percent,
      color: 'text-purple-600 dark:text-purple-400',
      bg: 'bg-purple-100 dark:bg-purple-900/30',
      span: 'sm:col-span-1',
    },
    {
      label: 'Avg. Order Value',
      value: metrics ? formatTZS(metrics.avg_order_value) : '—',
      icon: ShoppingCart,
      color: 'text-orange-600 dark:text-orange-400',
      bg: 'bg-orange-100 dark:bg-orange-900/30',
      span: 'sm:col-span-1',
    },
  ];

  const categoryChartData = (metrics?.top_categories || []).slice(0, 8);

  const topSellers = metrics?.top_sellers || [];
  const maxSellerRevenue = topSellers.length
    ? Math.max(...topSellers.map((s) => s.revenue), 1)
    : 1;

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
              <BarChart3 className="w-7 h-7 text-emerald-600" />
              Platform Analytics
            </h1>
            <p className="text-muted-foreground mt-1">
              Comprehensive platform performance metrics and insights
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 text-xs px-2.5 py-1">
              <Zap className="w-3 h-3 mr-1" />
              Live Data
            </Badge>
            <Button
              variant="outline"
              className="gap-2 shrink-0"
              onClick={() => navigate({ view: 'admin-dashboard' })}
            >
              <ArrowUpRight className="w-4 h-4" />
              Dashboard
            </Button>
          </div>
        </motion.div>

        {/* Top KPI Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {kpiCards.map((card, index) => (
            <motion.div
              key={card.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.03 * index }}
              className={card.span}
            >
              <Card className="border-0 shadow-md shadow-black/5 hover:shadow-lg transition-shadow h-full">
                <CardContent className="p-4 sm:p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div
                      className={`w-10 h-10 rounded-xl flex items-center justify-center ${card.bg}`}
                    >
                      <card.icon className={`w-5 h-5 ${card.color}`} />
                    </div>
                  </div>
                  {isLoading ? (
                    <Skeleton className="h-7 w-24 mb-1" />
                  ) : (
                    <p className="text-xl sm:text-2xl font-bold text-foreground truncate">
                      {card.value}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">{card.label}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Charts & Data Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top Categories Bar Chart */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.22 }}
          >
            <Card className="border-0 shadow-md shadow-black/5 h-full">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Crown className="w-5 h-5 text-emerald-600" />
                  Top Categories
                </CardTitle>
                <CardDescription>Listing count by category</CardDescription>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <Skeleton className="h-[300px] w-full rounded-xl" />
                ) : categoryChartData.length > 0 ? (
                  <div className="h-[300px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={categoryChartData} layout="vertical" margin={{ left: 10, right: 10 }}>
                        <CartesianGrid
                          strokeDasharray="3 3"
                          className="stroke-muted"
                          horizontal={false}
                        />
                        <XAxis
                          type="number"
                          tick={{
                            fill: 'hsl(var(--muted-foreground))',
                            fontSize: 11,
                          }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          type="category"
                          dataKey="category"
                          width={110}
                          tick={{
                            fill: 'hsl(var(--muted-foreground))',
                            fontSize: 11,
                          }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          contentStyle={CHART_TOOLTIP_STYLE}
                          cursor={{ fill: 'hsl(var(--muted) / 0.3)' }}
                          formatter={(value: number) => [value, 'Listings']}
                        />
                        <Bar
                          dataKey="count"
                          name="Listings"
                          radius={[0, 4, 4, 0]}
                          maxBarSize={28}
                        >
                          {categoryChartData.map((_, index) => (
                            <rect
                              key={`cell-${index}`}
                              fill={CHART_COLORS[index % CHART_COLORS.length]}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="text-center py-16 text-muted-foreground">
                    <BarChart3 className="w-10 h-10 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">No category data available.</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>

          {/* Top Sellers Table */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.28 }}
          >
            <Card className="border-0 shadow-md shadow-black/5 h-full">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Star className="w-5 h-5 text-emerald-600" />
                  Top Sellers
                </CardTitle>
                <CardDescription>By revenue and order performance</CardDescription>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Skeleton key={i} className="h-16 w-full" />
                    ))}
                  </div>
                ) : topSellers.length > 0 ? (
                  <div className="space-y-1">
                    {/* Desktop Table */}
                    <div className="hidden sm:block overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-12">#</TableHead>
                            <TableHead>Seller</TableHead>
                            <TableHead className="text-right">Revenue</TableHead>
                            <TableHead className="text-right">Orders</TableHead>
                            <TableHead className="w-32 hidden md:table-cell">
                              Performance
                            </TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {topSellers.map((seller, index) => (
                            <TableRow key={index}>
                              <TableCell>
                                <Badge
                                  variant="secondary"
                                  className={`text-xs font-bold w-7 h-7 flex items-center justify-center p-0 rounded-full ${
                                    index === 0
                                      ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                                      : index === 1
                                        ? 'bg-gray-200 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
                                        : index === 2
                                          ? 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400'
                                          : ''
                                  }`}
                                >
                                  {index + 1}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <div className="flex items-center gap-2">
                                  <Avatar className="h-7 w-7">
                                    <AvatarFallback className="text-[10px]">
                                      {seller.seller
                                        .split(' ')
                                        .map((w) => w[0])
                                        .join('')
                                        .slice(0, 2)
                                        .toUpperCase()}
                                    </AvatarFallback>
                                  </Avatar>
                                  <span className="text-sm font-medium truncate max-w-[140px]">
                                    {seller.seller}
                                  </span>
                                </div>
                              </TableCell>
                              <TableCell className="text-right text-sm font-bold">
                                {formatTZS(seller.revenue)}
                              </TableCell>
                              <TableCell className="text-right text-sm">
                                {seller.orders}
                              </TableCell>
                              <TableCell className="hidden md:table-cell">
                                <Progress
                                  value={(seller.revenue / maxSellerRevenue) * 100}
                                  className="h-2"
                                />
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>

                    {/* Mobile Cards */}
                    <div className="sm:hidden space-y-3 max-h-[360px] overflow-y-auto">
                      {topSellers.map((seller, index) => (
                        <div
                          key={index}
                          className="flex items-center gap-3 py-3 border-b last:border-0"
                        >
                          <Badge
                            variant="secondary"
                            className={`text-xs font-bold w-6 h-6 flex items-center justify-center p-0 rounded-full shrink-0 ${
                              index === 0
                                ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                                : index === 1
                                  ? 'bg-gray-200 text-gray-800 dark:bg-gray-800 dark:text-gray-200'
                                  : index === 2
                                    ? 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400'
                                    : ''
                            }`}
                          >
                            {index + 1}
                          </Badge>
                          <Avatar className="h-8 w-8 shrink-0">
                            <AvatarFallback className="text-xs">
                              {seller.seller
                                .split(' ')
                                .map((w) => w[0])
                                .join('')
                                .slice(0, 2)
                                .toUpperCase()}
                            </AvatarFallback>
                          </Avatar>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between mb-1">
                              <p className="text-sm font-medium truncate">
                                {seller.seller}
                              </p>
                              <span className="text-sm font-bold shrink-0 ml-2">
                                {formatTZS(seller.revenue)}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Progress
                                value={(seller.revenue / maxSellerRevenue) * 100}
                                className="h-1.5 flex-1"
                              />
                              <span className="text-[10px] text-muted-foreground shrink-0">
                                {seller.orders} orders
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-16 text-muted-foreground">
                    <Star className="w-10 h-10 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">No seller data available.</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
