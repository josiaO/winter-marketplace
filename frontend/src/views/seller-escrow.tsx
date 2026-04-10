'use client';

import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Shield,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ArrowUpRight,
  Loader2,
  DollarSign,
  Wallet,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
import type { Transaction, TransactionStatus } from '@/types/api';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatTZS(amount: number): string {
  return `TZS ${amount.toLocaleString('en-TZ')}`;
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-TZ', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-TZ', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getEscrowStatusBadge(status: TransactionStatus) {
  const config: Record<TransactionStatus, { color: string; label: string; icon: React.ReactNode }> = {
    created: {
      color: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
      label: 'Created',
      icon: <Clock className="w-3 h-3 mr-1" />,
    },
    pending: {
      color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
      label: 'Pending',
      icon: <Clock className="w-3 h-3 mr-1" />,
    },
    paid: {
      color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
      label: 'Paid',
      icon: <CheckCircle2 className="w-3 h-3 mr-1" />,
    },
    completed: {
      color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
      label: 'Completed',
      icon: <CheckCircle2 className="w-3 h-3 mr-1" />,
    },
    released: {
      color: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
      label: 'Released',
      icon: <CheckCircle2 className="w-3 h-3 mr-1" />,
    },
    failed: {
      color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
      label: 'Failed',
      icon: <AlertTriangle className="w-3 h-3 mr-1" />,
    },
    refunded: {
      color: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
      label: 'Refunded',
      icon: <AlertTriangle className="w-3 h-3 mr-1" />,
    },
  };
  const c = config[status] || config.created;
  return (
    <Badge className={`${c.color} text-xs`}>
      {c.icon}
      {c.label}
    </Badge>
  );
}

// ─── Component ─────────────────────────────────────────────────────────────────

export function SellerEscrowPage() {
  const { navigate } = useUIStore();
  const { user, isAuthenticated } = useAuthStore();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [pageSize] = useState(10);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate({ view: 'login' });
      return;
    }
    if (!user?.is_seller) {
      toast.error('You must be a seller to view escrow transactions.');
      navigate({ view: 'home' });
      return;
    }

    async function loadEscrow() {
      setIsLoading(true);
      try {
        const result = await api.commerce.sellerEscrow({ page, page_size: pageSize });
        const data = result as any;
        setTransactions(data.results || []);
        setTotalCount(data.count || 0);
      } catch {
        toast.error('Failed to load escrow transactions.');
      } finally {
        setIsLoading(false);
      }
    }
    loadEscrow();
  }, [isAuthenticated, user, navigate, page, pageSize]);

  const summary = useMemo(() => {
    const totalHeld = transactions
      .filter((t) => t.status === 'pending' || t.status === 'paid')
      .reduce((sum, t) => sum + t.amount, 0);
    const totalReleased = transactions
      .filter((t) => t.status === 'released')
      .reduce((sum, t) => sum + t.net_amount, 0);
    const pendingCount = transactions.filter((t) => t.status === 'pending').length;
    return { totalHeld, totalReleased, pendingCount };
  }, [transactions]);

  const totalPages = Math.ceil(totalCount / pageSize);

  if (!isAuthenticated || !user) return null;

  const summaryCards = [
    {
      title: 'Total Held in Escrow',
      value: formatTZS(summary.totalHeld),
      icon: Shield,
      color: 'text-amber-600 dark:text-amber-400',
      bg: 'bg-amber-100 dark:bg-amber-900/30',
      description: 'Funds awaiting release',
    },
    {
      title: 'Total Released',
      value: formatTZS(summary.totalReleased),
      icon: CheckCircle2,
      color: 'text-green-600 dark:text-green-400',
      bg: 'bg-green-100 dark:bg-green-900/30',
      description: 'Transferred to your account',
    },
    {
      title: 'Pending Transactions',
      value: String(summary.pendingCount),
      icon: Clock,
      color: 'text-primary',
      bg: 'bg-primary/10',
      description: 'Awaiting payment or release',
    },
  ];

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center gap-2">
              <Shield className="w-7 h-7 text-primary" />
              Escrow
            </h1>
            <p className="text-muted-foreground mt-1">
              Track your escrow transactions and payment status
            </p>
          </div>
          <Button
            variant="outline"
            className="gap-2 shrink-0"
            onClick={() => navigate({ view: 'seller-dashboard' })}
          >
            <ArrowUpRight className="w-4 h-4" />
            Dashboard
          </Button>
        </motion.div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {summaryCards.map((card, index) => (
            <motion.div
              key={card.title}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * index }}
            >
              <Card className="border-0 shadow-md shadow-black/5 hover:shadow-lg transition-shadow">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between mb-3">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${card.bg}`}>
                      <card.icon className={`w-5 h-5 ${card.color}`} />
                    </div>
                  </div>
                  {isLoading ? (
                    <Skeleton className="h-8 w-28 mb-1" />
                  ) : (
                    <p className="text-2xl font-bold text-foreground">{card.value}</p>
                  )}
                  <p className="text-sm font-medium text-foreground mt-1">{card.title}</p>
                  <p className="text-xs text-muted-foreground">{card.description}</p>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* Transactions Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Wallet className="w-5 h-5 text-primary" />
                Escrow Transactions
              </CardTitle>
              <CardDescription>
                {totalCount} transaction{totalCount !== 1 ? 's' : ''} total
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-14 w-full" />
                  ))}
                </div>
              ) : transactions.length === 0 ? (
                <div className="text-center py-16">
                  <Shield className="w-12 h-12 mx-auto mb-3 text-muted-foreground/30" />
                  <h3 className="font-semibold text-foreground text-lg mb-1">
                    No escrow transactions
                  </h3>
                  <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                    Escrow transactions will appear here when buyers make payments for your listings.
                  </p>
                </div>
              ) : (
                <>
                  {/* Desktop Table */}
                  <div className="hidden md:block overflow-x-auto -mx-6 px-6">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Order Ref</TableHead>
                          <TableHead>Amount</TableHead>
                          <TableHead className="hidden lg:table-cell">Fee</TableHead>
                          <TableHead className="text-right">Net Amount</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="hidden sm:table-cell">Date</TableHead>
                          <TableHead className="hidden lg:table-cell">Method</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {transactions.map((txn) => (
                          <TableRow key={txn.id} className="hover:bg-muted/50">
                            <TableCell>
                              <span className="text-sm font-mono font-medium text-foreground">
                                #{txn.order}
                              </span>
                            </TableCell>
                            <TableCell>
                              <span className="text-sm text-foreground">
                                {formatTZS(txn.amount)}
                              </span>
                            </TableCell>
                            <TableCell className="hidden lg:table-cell">
                              <span className="text-sm text-red-500">
                                -{formatTZS(txn.fee)}
                              </span>
                            </TableCell>
                            <TableCell className="text-right">
                              <span className="text-sm font-bold text-foreground">
                                {formatTZS(txn.net_amount)}
                              </span>
                            </TableCell>
                            <TableCell>
                              {getEscrowStatusBadge(txn.status)}
                            </TableCell>
                            <TableCell className="hidden sm:table-cell">
                              <span className="text-xs text-muted-foreground">
                                {formatDateTime(txn.created_at)}
                              </span>
                            </TableCell>
                            <TableCell className="hidden lg:table-cell">
                              <span className="text-xs text-muted-foreground capitalize">
                                {txn.payment_method?.replace('_', ' ')}
                              </span>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  {/* Mobile Cards */}
                  <div className="md:hidden space-y-3">
                    {transactions.map((txn) => (
                      <div key={txn.id} className="rounded-lg border p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-mono font-medium">#{txn.order}</span>
                          {getEscrowStatusBadge(txn.status)}
                        </div>
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-xs text-muted-foreground">Amount</p>
                            <p className="text-sm font-semibold">{formatTZS(txn.amount)}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-xs text-muted-foreground">Net</p>
                            <p className="text-sm font-bold text-primary">{formatTZS(txn.net_amount)}</p>
                          </div>
                        </div>
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span className="capitalize">{txn.payment_method?.replace('_', ' ')}</span>
                          <span>{formatDate(txn.created_at)}</span>
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
                          className="gap-1"
                        >
                          <ChevronLeft className="w-4 h-4" />
                          Previous
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={page >= totalPages}
                          onClick={() => setPage((p) => p + 1)}
                          className="gap-1"
                        >
                          Next
                          <ChevronRight className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
