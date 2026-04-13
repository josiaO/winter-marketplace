'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Wallet,
  ArrowUpRight,
  Loader2,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  DollarSign,
  ArrowRight,
  XCircle,
  RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
import { formatTZS, formatDate } from '@/lib/helpers';
import type { Payout, PaginatedResponse } from '@/types/api';

const PAGE_SIZE = 20;

const payoutStatusConfig: Record<
  Payout['status'],
  { label: string; color: string; icon: typeof Clock; bgColor: string }
> = {
  pending: {
    label: 'Pending',
    color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    icon: Clock,
    bgColor: 'bg-yellow-100 dark:bg-yellow-900/30',
  },
  processing: {
    label: 'Processing',
    color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    icon: Loader2,
    bgColor: 'bg-blue-100 dark:bg-blue-900/30',
  },
  released: {
    label: 'Released',
    color: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
    icon: CheckCircle2,
    bgColor: 'bg-emerald-100 dark:bg-emerald-900/30',
  },
  failed: {
    label: 'Failed',
    color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    icon: XCircle,
    bgColor: 'bg-red-100 dark:bg-red-900/30',
  },
};

function PayoutStatusBadge({ status }: { status: Payout['status'] }) {
  const config = payoutStatusConfig[status];
  const Icon = config.icon;
  const isSpinning = status === 'processing';
  return (
    <Badge variant="secondary" className={`text-xs gap-1 ${config.color}`}>
      <Icon className={`w-3 h-3 ${isSpinning ? 'animate-spin' : ''}`} />
      {config.label}
    </Badge>
  );
}

export function AdminPayoutsPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [allPayouts, setAllPayouts] = useState<Payout[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>('pending');
  const [page, setPage] = useState(1);
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [serverStats, setServerStats] = useState<any>(null);

  const fetchPayouts = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Record<string, string | number> = {
        limit: 100,
      };
      if (activeTab !== 'all') params.status = activeTab;

      const res: any = await api.commerce.payouts(params);
      setAllPayouts(res.results);
      if (res.summary_stats) {
        setServerStats(res.summary_stats);
      }
    } catch {
      toast.error('Failed to load payouts.');
    } finally {
      setIsLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      router.push(routes.home());
      return;
    }
    fetchPayouts();
  }, [isAuthenticated, user, router, fetchPayouts]);

  const handleProcessPayout = async (id: number) => {
    setProcessingId(id);
    try {
      await api.commerce.processPayout(id);
      toast.success('Payout processed successfully.');
      fetchPayouts();
    } catch {
      toast.error('Failed to process payout.');
    } finally {
      setProcessingId(null);
    }
  };

  const handleRetryPayout = async (id: number) => {
    setProcessingId(id);
    try {
      await api.commerce.processPayout(id);
      toast.success('Payout retry initiated.');
      fetchPayouts();
    } catch {
      toast.error('Failed to retry payout.');
    } finally {
      setProcessingId(null);
    }
  };

  // Compute summary stats from all payouts fetched (not just current tab)
  const summaryStats = useMemo(() => {
    if (serverStats) {
      return {
        pendingCount: serverStats.pending?.count || 0,
        pendingAmount: serverStats.pending?.amount || 0,
        processingCount: serverStats.processing?.count || 0,
        releasedCount: serverStats.released?.count || 0,
        releasedAmount: serverStats.released?.amount || 0,
        failedCount: serverStats.failed?.count || 0,
        totalFees: serverStats.total_fees || 0,
      };
    }
    
    // Fallback to local filtering if server stats not yet available (though they should be)
    const list = allPayouts || [];
    const pending = list.filter((p) => p.status === 'pending');
    const processing = list.filter((p) => p.status === 'processing');
    const released = list.filter((p) => p.status === 'released');
    const failed = list.filter((p) => p.status === 'failed');
    return {
      pendingCount: pending.length,
      pendingAmount: pending.reduce((sum, p) => sum + p.net_amount, 0),
      processingCount: processing.length,
      releasedCount: released.length,
      releasedAmount: released.reduce((sum, p) => sum + p.net_amount, 0),
      failedCount: failed.length,
      totalFees: list.reduce((sum, p) => sum + p.fee, 0),
    };
  }, [allPayouts, serverStats]);

  if (!isAuthenticated || !user || user.role !== 'admin') return null;
  
  const payoutList = allPayouts || [];
  const totalPages = Math.ceil(payoutList.length / PAGE_SIZE);
  const paginatedPayouts = payoutList.slice(
    (page - 1) * PAGE_SIZE,
    page * PAGE_SIZE,
  );

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
              <Wallet className="w-7 h-7 text-emerald-600" />
              Payout Management
            </h1>
            <p className="text-muted-foreground mt-1">
              Review and process seller payout requests
            </p>
          </div>
          <Button
            variant="outline"
            className="gap-2 shrink-0"
            onClick={() => router.push(routes.adminDashboard())}
          >
            <ArrowUpRight className="w-4 h-4" />
            Back to Dashboard
          </Button>
        </motion.div>

        {/* Summary Cards */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="grid grid-cols-2 sm:grid-cols-4 gap-4"
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center shrink-0">
                <Clock className="w-5 h-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                {isLoading ? (
                  <Skeleton className="h-7 w-12 mb-1" />
                ) : (
                  <p className="text-2xl font-bold">{summaryStats.pendingCount}</p>
                )}
                <p className="text-xs text-muted-foreground">Pending</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-md shadow-black/5">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center shrink-0">
                <Loader2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                {isLoading ? (
                  <Skeleton className="h-7 w-12 mb-1" />
                ) : (
                  <p className="text-2xl font-bold">{summaryStats.processingCount}</p>
                )}
                <p className="text-xs text-muted-foreground">Processing</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-md shadow-black/5">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center shrink-0">
                <DollarSign className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div>
                {isLoading ? (
                  <Skeleton className="h-7 w-20 mb-1" />
                ) : (
                  <p className="text-2xl font-bold">
                    {formatTZS(summaryStats.releasedAmount)}
                  </p>
                )}
                <p className="text-xs text-muted-foreground">Total Released</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-md shadow-black/5">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-100 dark:bg-red-900/30 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400" />
              </div>
              <div>
                {isLoading ? (
                  <Skeleton className="h-7 w-12 mb-1" />
                ) : (
                  <p className="text-2xl font-bold">{summaryStats.failedCount}</p>
                )}
                <p className="text-xs text-muted-foreground">Failed</p>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Payouts Table with Tabs */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-0">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <CardTitle className="text-lg">All Payouts</CardTitle>
                  <CardDescription>Manage seller payout requests</CardDescription>
                </div>
                <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 text-xs px-2.5 py-1 w-fit">
                  {formatTZS(summaryStats.totalFees)} in fees collected
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <Tabs value={activeTab} onValueChange={(val) => { setActiveTab(val); setPage(1); }} className="w-full">
                <TabsList className="w-full sm:w-auto grid grid-cols-2 sm:grid-cols-4 mb-6">
                  <TabsTrigger value="pending" className="gap-1.5 text-xs sm:text-sm">
                    <Clock className="w-3.5 h-3.5 hidden sm:block" />
                    Pending
                    {summaryStats.pendingCount > 0 && (
                      <Badge variant="secondary" className="ml-1 h-5 min-w-5 px-1.5 text-[10px] bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">
                        {summaryStats.pendingCount}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="processing" className="gap-1.5 text-xs sm:text-sm">
                    <Loader2 className="w-3.5 h-3.5 hidden sm:block" />
                    Processing
                    {summaryStats.processingCount > 0 && (
                      <Badge variant="secondary" className="ml-1 h-5 min-w-5 px-1.5 text-[10px] bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                        {summaryStats.processingCount}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="released" className="gap-1.5 text-xs sm:text-sm">
                    <CheckCircle2 className="w-3.5 h-3.5 hidden sm:block" />
                    Released
                    {summaryStats.releasedCount > 0 && (
                      <Badge variant="secondary" className="ml-1 h-5 min-w-5 px-1.5 text-[10px] bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                        {summaryStats.releasedCount}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="failed" className="gap-1.5 text-xs sm:text-sm">
                    <XCircle className="w-3.5 h-3.5 hidden sm:block" />
                    Failed
                    {summaryStats.failedCount > 0 && (
                      <Badge variant="secondary" className="ml-1 h-5 min-w-5 px-1.5 text-[10px] bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                        {summaryStats.failedCount}
                      </Badge>
                    )}
                  </TabsTrigger>
                </TabsList>

                {['pending', 'processing', 'released', 'failed'].map((tab) => (
                  <TabsContent key={tab} value={tab}>
                    {isLoading ? (
                      <div className="space-y-3">
                        {Array.from({ length: 6 }).map((_, i) => (
                          <Skeleton key={i} className="h-14 w-full" />
                        ))}
                      </div>
                    ) : payoutList.length === 0 ? (
                      <div className="text-center py-16">
                        <Wallet className="w-12 h-12 mx-auto mb-3 text-muted-foreground/30" />
                        <h3 className="font-semibold text-foreground text-lg mb-1">No payouts found</h3>
                        <p className="text-sm text-muted-foreground">
                          No {tab} payouts at the moment.
                        </p>
                      </div>
                    ) : (
                      <>
                        {/* Desktop Table */}
                        <div className="hidden md:block overflow-x-auto">
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead>ID</TableHead>
                                <TableHead>Seller</TableHead>
                                <TableHead>Amount</TableHead>
                                <TableHead>Fee</TableHead>
                                <TableHead>Net Amount</TableHead>
                                <TableHead>Method</TableHead>
                                <TableHead>Payment Ref</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead className="hidden lg:table-cell">Created</TableHead>
                                <TableHead className="hidden xl:table-cell">Released</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {paginatedPayouts.map((payout) => (
                                <TableRow key={payout.id}>
                                  <TableCell className="font-mono text-sm">
                                    #{payout.id}
                                  </TableCell>
                                  <TableCell className="text-sm">
                                    Seller #{payout.seller}
                                  </TableCell>
                                  <TableCell className="text-sm">
                                    {formatTZS(payout.amount)}
                                  </TableCell>
                                  <TableCell className="text-sm text-red-500">
                                    -{formatTZS(payout.fee)}
                                  </TableCell>
                                  <TableCell className="text-sm font-bold">
                                    {formatTZS(payout.net_amount)}
                                  </TableCell>
                                  <TableCell className="text-sm text-muted-foreground capitalize">
                                    {payout.payout_method || '—'}
                                  </TableCell>
                                  <TableCell className="text-xs text-muted-foreground font-mono">
                                    {payout.payment_ref
                                      ? payout.payment_ref.length > 12
                                        ? `${payout.payment_ref.slice(0, 12)}...`
                                        : payout.payment_ref
                                      : '—'}
                                  </TableCell>
                                  <TableCell>
                                    <PayoutStatusBadge status={payout.status} />
                                  </TableCell>
                                  <TableCell className="hidden lg:table-cell text-xs text-muted-foreground">
                                    {formatDate(payout.created_at)}
                                  </TableCell>
                                  <TableCell className="hidden xl:table-cell text-xs text-muted-foreground">
                                    {payout.released_at
                                      ? formatDate(payout.released_at)
                                      : '—'}
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <div className="flex items-center justify-end gap-1">
                                      {payout.status === 'pending' && (
                                        <Button
                                          size="sm"
                                          className="h-7 text-xs gap-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                                          onClick={() => handleProcessPayout(payout.id)}
                                          disabled={processingId === payout.id}
                                        >
                                          {processingId === payout.id ? (
                                            <Loader2 className="w-3 h-3 animate-spin" />
                                          ) : (
                                            <ArrowRight className="w-3 h-3" />
                                          )}
                                          Process
                                        </Button>
                                      )}
                                      {payout.status === 'processing' && (
                                        <Badge variant="secondary" className="text-xs">
                                          In Progress
                                        </Badge>
                                      )}
                                      {payout.status === 'failed' && (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-7 text-xs gap-1 text-amber-600 border-amber-200 hover:bg-amber-50 dark:border-amber-800 dark:text-amber-400 dark:hover:bg-amber-900/20"
                                          onClick={() => handleRetryPayout(payout.id)}
                                          disabled={processingId === payout.id}
                                        >
                                          {processingId === payout.id ? (
                                            <Loader2 className="w-3 h-3 animate-spin" />
                                          ) : (
                                            <RefreshCw className="w-3 h-3" />
                                          )}
                                          Retry
                                        </Button>
                                      )}
                                    </div>
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>

                        {/* Mobile Cards */}
                        <div className="md:hidden space-y-3">
                          {paginatedPayouts.map((payout) => (
                            <div key={payout.id} className="border rounded-lg p-4 space-y-3">
                              <div className="flex items-start justify-between">
                                <div>
                                  <p className="text-sm font-mono font-medium">
                                    #{payout.id}
                                  </p>
                                  <p className="text-xs text-muted-foreground">
                                    Seller #{payout.seller}
                                  </p>
                                </div>
                                <PayoutStatusBadge status={payout.status} />
                              </div>
                              <div className="grid grid-cols-3 gap-2">
                                <div>
                                  <p className="text-[10px] text-muted-foreground uppercase">Amount</p>
                                  <p className="text-sm">{formatTZS(payout.amount)}</p>
                                </div>
                                <div>
                                  <p className="text-[10px] text-muted-foreground uppercase">Fee</p>
                                  <p className="text-sm text-red-500">-{formatTZS(payout.fee)}</p>
                                </div>
                                <div>
                                  <p className="text-[10px] text-muted-foreground uppercase">Net</p>
                                  <p className="text-sm font-bold">
                                    {formatTZS(payout.net_amount)}
                                  </p>
                                </div>
                              </div>
                              {(payout.payout_method || payout.payment_ref) && (
                                <div className="text-[10px] text-muted-foreground space-y-0.5">
                                  {payout.payout_method && (
                                    <p>
                                      Method: <span className="capitalize">{payout.payout_method}</span>
                                    </p>
                                  )}
                                  {payout.payment_ref && <p>Ref: {payout.payment_ref}</p>}
                                </div>
                              )}
                              <div className="flex items-center justify-between pt-1">
                                <span className="text-[10px] text-muted-foreground">
                                  {formatDate(payout.created_at)}
                                  {payout.released_at && (
                                    <span className="text-emerald-600 dark:text-emerald-400">
                                      {' · Released '}
                                      {formatDate(payout.released_at)}
                                    </span>
                                  )}
                                </span>
                                <div className="flex items-center gap-1.5">
                                  {payout.status === 'pending' && (
                                    <Button
                                      size="sm"
                                      className="h-7 text-xs gap-1 bg-emerald-600 hover:bg-emerald-700 text-white"
                                      onClick={() => handleProcessPayout(payout.id)}
                                      disabled={processingId === payout.id}
                                    >
                                      {processingId === payout.id ? (
                                        <Loader2 className="w-3 h-3 animate-spin" />
                                      ) : (
                                        <ArrowRight className="w-3 h-3" />
                                      )}
                                      Process
                                    </Button>
                                  )}
                                  {payout.status === 'failed' && (
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="h-7 text-xs gap-1 text-amber-600 border-amber-200"
                                      onClick={() => handleRetryPayout(payout.id)}
                                      disabled={processingId === payout.id}
                                    >
                                      {processingId === payout.id ? (
                                        <Loader2 className="w-3 h-3 animate-spin" />
                                      ) : (
                                        <RefreshCw className="w-3 h-3" />
                                      )}
                                      Retry
                                    </Button>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>

                        {/* Pagination */}
                        {totalPages > 1 && (
                          <div className="flex items-center justify-between mt-4 pt-4 border-t">
                            <p className="text-sm text-muted-foreground">
                              Page {page} of {totalPages}
                            </p>
                            <div className="flex items-center gap-2">
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={page <= 1}
                                onClick={() => setPage((p) => p - 1)}
                              >
                                <ChevronLeft className="w-4 h-4" />
                                Previous
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                disabled={page >= totalPages}
                                onClick={() => setPage((p) => p + 1)}
                              >
                                Next
                                <ChevronRight className="w-4 h-4" />
                              </Button>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </TabsContent>
                ))}
              </Tabs>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
