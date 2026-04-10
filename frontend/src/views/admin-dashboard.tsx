'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Users,
  Store,
  Package,
  ShoppingCart,
  DollarSign,
  Shield,
  Clock,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  TrendingUp,
  Eye,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, formatDate, getInitials, getRelativeTime } from '@/lib/helpers';
import type { AdminStats, GrowthCharts, GrowthChartData } from '@/types/api';

// ---------------------------------------------------------------------------
// Animation variants
// ---------------------------------------------------------------------------

const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.04 } },
};

const item = {
  hidden: { opacity: 0, y: 18 },
  show: { opacity: 1, y: 0 },
};

// ---------------------------------------------------------------------------
// Metric card definitions
// ---------------------------------------------------------------------------

interface MetricCardDef {
  label: string;
  key: keyof AdminStats;
  format: 'number' | 'currency';
  icon: React.ElementType;
  color: string;
  bg: string;
}

const metricCards: MetricCardDef[] = [
  { label: 'Total Users', key: 'total_users', format: 'number', icon: Users, color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-950/40' },
  { label: 'Total Sellers', key: 'total_sellers', format: 'number', icon: Store, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-950/40' },
  { label: 'Total Listings', key: 'total_listings', format: 'number', icon: Package, color: 'text-teal-600 dark:text-teal-400', bg: 'bg-teal-50 dark:bg-teal-950/40' },
  { label: 'Total Orders', key: 'total_orders', format: 'number', icon: ShoppingCart, color: 'text-orange-600 dark:text-orange-400', bg: 'bg-orange-50 dark:bg-orange-950/40' },
  { label: 'Total Revenue', key: 'total_revenue', format: 'currency', icon: DollarSign, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-950/40' },
  { label: 'Escrow Balance', key: 'total_escrow_balance', format: 'currency', icon: Shield, color: 'text-teal-600 dark:text-teal-400', bg: 'bg-teal-50 dark:bg-teal-950/40' },
  { label: 'Pending Verifications', key: 'pending_verifications', format: 'number', icon: Clock, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-950/40' },
  { label: 'Open Disputes', key: 'open_disputes', format: 'number', icon: AlertTriangle, color: 'text-red-600 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-950/40' },
];

// ---------------------------------------------------------------------------
// Quick action definitions
// ---------------------------------------------------------------------------

interface QuickActionDef {
  label: string;
  description: string;
  icon: React.ElementType;
  color: string;
  bg: string;
  view:
    | 'admin-users'
    | 'admin-verifications'
    | 'admin-listings'
    | 'admin-reports'
    | 'admin-disputes'
    | 'admin-payouts'
    | 'admin-analytics'
    | 'admin-plans'
    | 'admin-catalog';
}

const quickActions: QuickActionDef[] = [
  { label: 'Manage Users', description: 'View and manage all platform users', icon: Users, color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-950/40', view: 'admin-users' },
  { label: 'Verify Sellers', description: 'Review seller verification requests', icon: Shield, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-950/40', view: 'admin-verifications' },
  { label: 'Moderate Listings', description: 'Review and manage marketplace listings', icon: Package, color: 'text-teal-600 dark:text-teal-400', bg: 'bg-teal-50 dark:bg-teal-950/40', view: 'admin-listings' },
  { label: 'Catalog', description: 'Manage categories and dynamic fields', icon: Store, color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-950/40', view: 'admin-catalog' },
  { label: 'View Reports', description: 'Handle abuse and fraud reports', icon: AlertTriangle, color: 'text-red-600 dark:text-red-400', bg: 'bg-red-50 dark:bg-red-950/40', view: 'admin-reports' },
  { label: 'Disputes', description: 'Resolve order disputes and conflicts', icon: Clock, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-950/40', view: 'admin-disputes' },
  { label: 'Payouts', description: 'Manage seller payout requests', icon: DollarSign, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-950/40', view: 'admin-payouts' },
  { label: 'Analytics', description: 'View platform performance metrics', icon: BarChart3, color: 'text-teal-600 dark:text-teal-400', bg: 'bg-teal-50 dark:bg-teal-950/40', view: 'admin-analytics' },
  { label: 'Plans & Features', description: 'Manage subscription plans', icon: Eye, color: 'text-pink-600 dark:text-pink-400', bg: 'bg-pink-50 dark:bg-pink-950/40', view: 'admin-plans' },
];

// ---------------------------------------------------------------------------
// Order status helper
// ---------------------------------------------------------------------------

function orderStatusColor(status: string) {
  if (status === 'completed' || status === 'delivered') return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400';
  if (status === 'pending' || status === 'confirmed') return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400';
  if (status === 'disputed') return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
  if (status === 'cancelled' || status === 'refunded') return 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400';
  return 'bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-400';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AdminDashboardPage() {
  const navigate = useUIStore((s) => s.navigate);
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [growthData, setGrowthData] = useState<GrowthChartData[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // ── Auth guard ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      navigate({ view: 'home' });
      return;
    }

    async function loadData() {
      setIsLoading(true);
      try {
        const [adminStats, charts] = await Promise.all([
          api.insights.adminStats(),
          api.insights.growthCharts({ period: 'daily' }),
        ]);
        setStats(adminStats);
        // Take last 30 days
        setGrowthData((charts.daily ?? []).slice(-30));
      } catch {
        toast.error('Failed to load admin dashboard data.');
      } finally {
        setIsLoading(false);
      }
    }
    loadData();
  }, [isAuthenticated, user, navigate]);

  if (!isAuthenticated || !user || user.role !== 'admin') return null;

  // ── Chart data ─────────────────────────────────────────────────────────
  const chartData = growthData.map((d) => ({
    ...d,
    date: d.date
      ? new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      : d.date,
  }));

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div className="min-h-[80vh] px-4 py-6 sm:py-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* ── Header ─────────────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center gap-2">
              <Shield className="w-7 h-7 text-emerald-600" />
              Admin Dashboard
            </h1>
            <p className="text-muted-foreground mt-1">
              Platform overview and management controls
            </p>
          </div>
          <Badge
            variant="secondary"
            className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 text-sm px-3 py-1 w-fit"
          >
            Admin Panel
          </Badge>
        </motion.div>

        {/* ── Metric Cards (2 cols mobile, 4 cols desktop) ──────────────── */}
        <motion.div
          variants={container}
          initial="hidden"
          animate="show"
          className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4"
        >
          {metricCards.map((card) => {
            const raw = stats?.[card.key] ?? 0;
            const display = card.format === 'currency' ? formatTZS(raw as number) : (raw as number).toLocaleString();

            return (
              <motion.div key={card.key} variants={item}>
                <Card className="border-0 shadow-md shadow-black/5 hover:shadow-lg transition-shadow">
                  <CardContent className="p-4 sm:p-5">
                    <div className="flex items-center justify-between mb-3">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${card.bg}`}>
                        <card.icon className={`w-5 h-5 ${card.color}`} />
                      </div>
                    </div>
                    {isLoading ? (
                      <Skeleton className="h-7 w-24 mb-1" />
                    ) : (
                      <p className="text-xl sm:text-2xl font-bold text-foreground tracking-tight">{display}</p>
                    )}
                    <p className="text-xs text-muted-foreground mt-1">{card.label}</p>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </motion.div>

        {/* ── Growth Chart ───────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-emerald-600" />
                Orders Over Time (Last 30 Days)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <Skeleton className="h-[320px] w-full" />
              ) : chartData.length > 0 ? (
                <div className="h-[320px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis
                        dataKey="date"
                        className="text-xs"
                        tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                        interval="preserveStartEnd"
                      />
                      <YAxis
                        className="text-xs"
                        tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                        width={40}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'hsl(var(--background))',
                          border: '1px solid hsl(var(--border))',
                          borderRadius: '8px',
                          fontSize: '12px',
                          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: '12px' }} />
                      <Line
                        type="monotone"
                        dataKey="orders"
                        stroke="#0d9488"
                        strokeWidth={2}
                        dot={false}
                        name="Orders"
                      />
                      <Line
                        type="monotone"
                        dataKey="revenue"
                        stroke="#10b981"
                        strokeWidth={2}
                        dot={false}
                        name="Revenue"
                      />
                      <Line
                        type="monotone"
                        dataKey="users"
                        stroke="#14b8a6"
                        strokeWidth={1.5}
                        dot={false}
                        name="Users"
                        strokeDasharray="5 5"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <div className="text-center py-16 text-muted-foreground">
                  <BarChart3 className="w-10 h-10 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No growth data available.</p>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* ── Quick Actions ──────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Quick Actions</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
              {quickActions.map((action) => (
                <Button
                  key={action.view}
                  variant="outline"
                  className="justify-start gap-3 h-auto py-3 hover:border-emerald-300 transition-colors"
                  onClick={() => navigate({ view: action.view })}
                >
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${action.bg}`}>
                    <action.icon className={`w-4 h-4 ${action.color}`} />
                  </div>
                  <div className="text-left min-w-0">
                    <p className="text-sm font-medium truncate">{action.label}</p>
                    <p className="text-[10px] text-muted-foreground truncate">{action.description}</p>
                  </div>
                  <ArrowUpRight className="w-3.5 h-3.5 ml-auto text-muted-foreground shrink-0" />
                </Button>
              ))}
            </CardContent>
          </Card>
        </motion.div>

        {/* ── Recent Users + Recent Orders ───────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Users */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <Card className="border-0 shadow-md shadow-black/5 h-full">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Users className="w-5 h-5 text-emerald-600" />
                  Recent Users
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1.5 text-emerald-600 hover:text-emerald-700"
                  onClick={() => navigate({ view: 'admin-users' })}
                >
                  View All <ArrowUpRight className="w-3.5 h-3.5" />
                </Button>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Skeleton key={i} className="h-10 w-full" />
                    ))}
                  </div>
                ) : stats?.recent_users && stats.recent_users.length > 0 ? (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>User</TableHead>
                          <TableHead className="hidden sm:table-cell">Role</TableHead>
                          <TableHead className="hidden sm:table-cell">Joined</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {stats.recent_users.slice(0, 5).map((u) => (
                          <TableRow key={u.id}>
                            <TableCell>
                              <div className="flex items-center gap-2.5">
                                <Avatar className="h-7 w-7">
                                  <AvatarImage src={u.avatar || undefined} />
                                  <AvatarFallback className="text-xs bg-emerald-50 dark:bg-emerald-950/40">
                                    {getInitials(`${u.first_name} ${u.last_name}`)}
                                  </AvatarFallback>
                                </Avatar>
                                <div className="min-w-0">
                                  <p className="text-sm font-medium truncate">
                                    {u.first_name || u.username}
                                  </p>
                                  <p className="text-xs text-muted-foreground truncate">{u.email}</p>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell className="hidden sm:table-cell">
                              <Badge
                                variant="secondary"
                                className={`text-xs capitalize ${
                                  u.role === 'admin'
                                    ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                                    : u.role === 'seller'
                                      ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400'
                                      : 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400'
                                }`}
                              >
                                {u.role}
                              </Badge>
                            </TableCell>
                            <TableCell className="hidden sm:table-cell text-xs text-muted-foreground">
                              {getRelativeTime(u.date_joined)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <Users className="w-10 h-10 mx-auto mb-2 opacity-20" />
                    <p className="text-sm">No recent users.</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>

          {/* Recent Orders */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
          >
            <Card className="border-0 shadow-md shadow-black/5 h-full">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  <ShoppingCart className="w-5 h-5 text-emerald-600" />
                  Recent Orders
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1.5 text-emerald-600 hover:text-emerald-700"
                  onClick={() => navigate({ view: 'admin-disputes' })}
                >
                  View All <ArrowUpRight className="w-3.5 h-3.5" />
                </Button>
              </CardHeader>
              <CardContent>
                {isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Skeleton key={i} className="h-12 w-full" />
                    ))}
                  </div>
                ) : stats?.recent_orders && stats.recent_orders.length > 0 ? (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Order #</TableHead>
                          <TableHead className="hidden sm:table-cell">Buyer</TableHead>
                          <TableHead>Total</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="hidden md:table-cell">Date</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {stats.recent_orders.slice(0, 5).map((order) => (
                          <TableRow key={order.id}>
                            <TableCell className="font-medium text-sm font-mono">
                              #{order.order_number?.slice(-8) || order.id}
                            </TableCell>
                            <TableCell className="hidden sm:table-cell text-sm">
                              {typeof order.buyer === 'object'
                                ? `${order.buyer.first_name || ''} ${order.buyer.last_name || ''}`.trim() || order.buyer.username
                                : `User #${order.buyer}`}
                            </TableCell>
                            <TableCell className="text-sm font-medium">
                              {formatTZS(order.total)}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant="secondary"
                                className={`text-xs capitalize ${orderStatusColor(order.status)}`}
                              >
                                {order.status === 'completed' ? (
                                  <CheckCircle2 className="w-3 h-3 mr-1" />
                                ) : order.status === 'disputed' ? (
                                  <XCircle className="w-3 h-3 mr-1" />
                                ) : null}
                                {order.status}
                              </Badge>
                            </TableCell>
                            <TableCell className="hidden md:table-cell text-xs text-muted-foreground">
                              {formatDate(order.created_at)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <ShoppingCart className="w-10 h-10 mx-auto mb-2 opacity-20" />
                    <p className="text-sm">No recent orders.</p>
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
