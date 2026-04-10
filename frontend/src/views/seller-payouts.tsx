'use client';

import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Wallet,
  Clock,
  CheckCircle2,
  AlertTriangle,
  ArrowUpRight,
  DollarSign,
  Info,
  CreditCard,
  WalletIcon,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
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
import { formatTZS, formatDate, formatDateTime } from '@/lib/helpers';
import type { Payout, PaginatedResponse } from '@/types/api';

export function SellerPayoutsPage() {
  const { navigate } = useUIStore();
  const { user, isAuthenticated } = useAuthStore();
  const [payouts, setPayouts] = useState<Payout[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate({ view: 'login' });
      return;
    }
    if (!user?.is_seller) {
      toast.error('You must be a seller to view payouts.');
      navigate({ view: 'home' });
      return;
    }

    async function loadPayouts() {
      try {
        const data = await api.commerce.payouts();
        const items = (data as PaginatedResponse<Payout>).results ?? (Array.isArray(data) ? data : []);
        setPayouts(items as Payout[]);
      } catch {
        toast.error('Failed to load payouts.');
      } finally {
        setIsLoading(false);
      }
    }
    loadPayouts();
  }, [isAuthenticated, user, navigate]);

  const summary = useMemo(() => {
    const totalEarned = payouts.reduce((sum, p) => sum + p.net_amount, 0);
    const totalFee = payouts.reduce((sum, p) => sum + p.fee, 0);
    const pendingAmount = payouts
      .filter((p) => p.status === 'pending' || p.status === 'processing')
      .reduce((sum, p) => sum + p.net_amount, 0);
    const releasedAmount = payouts
      .filter((p) => p.status === 'released')
      .reduce((sum, p) => sum + p.net_amount, 0);
    return { totalEarned, totalFee, pendingAmount, releasedAmount };
  }, [payouts]);

  const getPayoutStatusBadge = (status: string) => {
    switch (status) {
      case 'pending':
        return (
          <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400 text-xs">
            <Clock className="w-3 h-3 mr-1" />
            Pending
          </Badge>
        );
      case 'processing':
        return (
          <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400 text-xs">
            <Clock className="w-3 h-3 mr-1 animate-spin" />
            Processing
          </Badge>
        );
      case 'released':
        return (
          <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 text-xs">
            <CheckCircle2 className="w-3 h-3 mr-1" />
            Released
          </Badge>
        );
      case 'failed':
        return (
          <Badge className="bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400 text-xs">
            <AlertTriangle className="w-3 h-3 mr-1" />
            Failed
          </Badge>
        );
      default:
        return (
          <Badge variant="secondary" className="text-xs">
            {status}
          </Badge>
        );
    }
  };

  if (!isAuthenticated || !user) return null;

  const summaryCards = [
    {
      title: 'Total Earned',
      value: formatTZS(summary.totalEarned),
      icon: DollarSign,
      color: 'text-green-600 dark:text-green-400',
      bg: 'bg-green-100 dark:bg-green-900/30',
      description: `Fees: ${formatTZS(summary.totalFee)}`,
    },
    {
      title: 'Pending',
      value: formatTZS(summary.pendingAmount),
      icon: Clock,
      color: 'text-amber-600 dark:text-amber-400',
      bg: 'bg-amber-100 dark:bg-amber-900/30',
      description: 'Awaiting release',
    },
    {
      title: 'Released',
      value: formatTZS(summary.releasedAmount),
      icon: CheckCircle2,
      color: 'text-primary',
      bg: 'bg-primary/10',
      description: 'Transferred to your account',
    },
  ];

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center gap-2">
              <Wallet className="w-7 h-7 text-primary" />
              Payouts
            </h1>
            <p className="text-muted-foreground mt-1">
              Track your earnings and payout history
            </p>
          </div>
          <Button
            variant="outline"
            className="gap-2 shrink-0"
            onClick={() => navigate({ view: 'seller-dashboard' })}
          >
            <ArrowUpRight className="w-4 h-4" />
            Back to Dashboard
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

        {/* Payout Schedule Info */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <Alert className="border-primary/20 bg-primary/5 dark:bg-primary/5">
            <Info className="h-4 w-4 text-primary" />
            <AlertDescription className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">Payout Schedule: </span>
              Payouts are released 48 hours after delivery confirmation. Funds are transferred directly
              to your registered bank account. Processing typically takes 1-2 business days.
            </AlertDescription>
          </Alert>
        </motion.div>

        {/* Payouts Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <CreditCard className="w-5 h-5 text-primary" />
                Payout History
              </CardTitle>
              <CardDescription>
                {payouts.length} payout{payouts.length !== 1 ? 's' : ''} total
              </CardDescription>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-14 w-full" />
                  ))}
                </div>
              ) : payouts.length === 0 ? (
                <div className="text-center py-16">
                  <WalletIcon className="w-12 h-12 mx-auto mb-3 text-muted-foreground/30" />
                  <h3 className="font-semibold text-foreground text-lg mb-1">
                    No payouts yet
                  </h3>
                  <p className="text-sm text-muted-foreground max-w-sm mx-auto">
                    Payouts will appear here once your delivered orders are confirmed and processed.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto -mx-6 px-6">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Date</TableHead>
                        <TableHead className="text-right">Amount</TableHead>
                        <TableHead className="text-right hidden sm:table-cell">Fee</TableHead>
                        <TableHead className="text-right">Net Amount</TableHead>
                        <TableHead>Method</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {payouts.map((payout) => (
                        <TableRow key={payout.id} className="hover:bg-muted/50">
                          <TableCell>
                            <div>
                              <p className="text-sm font-medium text-foreground">
                                {formatDate(payout.created_at)}
                              </p>
                              {payout.released_at && (
                                <p className="text-xs text-muted-foreground">
                                  Released: {formatDate(payout.released_at)}
                                </p>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-right">
                            <span className="text-sm text-muted-foreground line-through">
                              {formatTZS(payout.amount)}
                            </span>
                          </TableCell>
                          <TableCell className="text-right hidden sm:table-cell">
                            <span className="text-sm text-red-500 font-medium">
                              -{formatTZS(payout.fee)}
                            </span>
                          </TableCell>
                          <TableCell className="text-right">
                            <span className="text-sm font-bold text-foreground">
                              {formatTZS(payout.net_amount)}
                            </span>
                          </TableCell>
                          <TableCell>
                            <span className="text-sm text-muted-foreground capitalize">
                              {payout.payout_method || '—'}
                            </span>
                          </TableCell>
                          <TableCell>{getPayoutStatusBadge(payout.status)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
