'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, Loader2, Wallet } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { routes } from '@/lib/routes';
import { api } from '@/lib/api-client';
import { formatTZS } from '@/lib/helpers';
import type { CommerceSellerStats } from '@/types/api';
import { useAuthStore } from '@/store';

type PayoutMethodRow = {
  id: number | string;
  provider?: string;
  type?: string;
  account_number?: string;
  is_primary?: boolean;
  masked?: string;
};

function maskAccount(s: string | undefined): string {
  if (!s || s.length < 4) return '****';
  return `****${s.replace(/\D/g, '').slice(-4)}`;
}

export function SellerWithdrawPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [stats, setStats] = useState<CommerceSellerStats | null>(null);
  const [methods, setMethods] = useState<PayoutMethodRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [amountStr, setAmountStr] = useState('');
  const [selectedId, setSelectedId] = useState<string | number | null>(null);
  const [step, setStep] = useState<'form' | 'done'>('form');
  const [submitting, setSubmitting] = useState(false);

  const available = Math.max(0, stats?.escrow?.available_for_withdrawal ?? 0);
  const platformFee = 0;

  useEffect(() => {
    if (!isAuthenticated || !user?.is_seller) return;
    void (async () => {
      try {
        const [s, pm] = await Promise.all([
          api.commerce.sellerStats() as Promise<CommerceSellerStats>,
          api.marketplace.sellerPaymentMethods.list().catch(() => []),
        ]);
        setStats(s);
        const list = Array.isArray(pm) ? pm : (pm as { results?: PayoutMethodRow[] }).results ?? [];
        setMethods(list as PayoutMethodRow[]);
        const primary = (list as PayoutMethodRow[]).find((m) => m.is_primary);
        if (primary) setSelectedId(primary.id);
        else if ((list as PayoutMethodRow[])[0]) setSelectedId((list as PayoutMethodRow[])[0].id);
      } catch {
        toast.error('Could not load withdrawal details.');
      } finally {
        setLoading(false);
      }
    })();
  }, [isAuthenticated, user]);

  useEffect(() => {
    if (available > 0 && !amountStr) {
      setAmountStr(String(Math.floor(available)));
    }
  }, [available, amountStr]);

  const amountNum = useMemo(() => {
    const n = parseFloat(amountStr.replace(/,/g, ''));
    return Number.isFinite(n) ? n : 0;
  }, [amountStr]);

  const receive = Math.max(0, amountNum - platformFee);

  const submit = async () => {
    if (!selectedId) {
      toast.error('Choose a payout account.');
      return;
    }
    if (amountNum <= 0 || amountNum > available) {
      toast.error('Enter a valid amount.');
      return;
    }
    setSubmitting(true);
    try {
      await api.commerce.requestWithdrawal({
        amount: amountNum,
        payout_method_id: selectedId,
      });
      setStep('done');
      setTimeout(() => router.push(routes.sellerDashboard()), 2800);
    } catch {
      toast.error(
        'We could not process this withdrawal right now. Your balance is safe. Try again in a few minutes or contact support.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (!isAuthenticated || !user?.is_seller) return null;

  return (
    <div className="space-y-6 max-w-lg mx-auto pb-12">
      <Button variant="ghost" className="px-0" onClick={() => router.push(routes.sellerWallet())}>
        ← Back to wallet
      </Button>

      <AnimatePresence mode="wait">
        {step === 'done' ? (
          <motion.div
            key="done"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border bg-card p-8 text-center space-y-3"
          >
            <CheckCircle2 className="w-12 h-12 text-emerald-600 mx-auto" />
            <h2 className="text-xl font-semibold">Withdrawal initiated</h2>
            <p className="text-sm text-muted-foreground">
              Funds typically arrive within minutes via M-Pesa once our team confirms the payout. You will see updates under
              Payouts.
            </p>
            <p className="text-xs text-muted-foreground">Taking you back to your dashboard…</p>
          </motion.div>
        ) : (
          <motion.div key="form" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <Card className="border-0 shadow-lg">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Wallet className="w-5 h-5" />
                  Withdraw
                </CardTitle>
                <CardDescription>Send money to your saved payout account.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <p className="text-sm text-muted-foreground">Available balance</p>
                  {loading ? (
                    <Skeleton className="h-10 w-40 mt-1" />
                  ) : (
                    <p className="text-2xl font-bold mt-1">{formatTZS(available)}</p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label>Send to</Label>
                  <div className="space-y-2">
                    {loading ? (
                      <Skeleton className="h-24 w-full" />
                    ) : methods.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        No payout accounts yet.{' '}
                        <button type="button" className="text-primary underline" onClick={() => router.push(routes.sellerPaymentMethod())}>
                          Add one
                        </button>
                      </p>
                    ) : (
                      methods.map((m) => {
                        const label = (m.provider || m.type || 'Account').replace(/_/g, ' ');
                        const masked = m.masked || maskAccount(m.account_number);
                        const active = selectedId === m.id;
                        return (
                          <button
                            key={String(m.id)}
                            type="button"
                            onClick={() => setSelectedId(m.id)}
                            className={cn(
                              'w-full text-left rounded-xl border-2 p-4 transition-colors',
                              active ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/40',
                            )}
                          >
                            <p className="font-semibold capitalize">{label}</p>
                            <p className="text-sm text-muted-foreground">{masked}</p>
                            {m.is_primary && (
                              <span className="text-xs font-medium text-emerald-600 mt-1 inline-block">Primary</span>
                            )}
                          </button>
                        );
                      })
                    )}
                    <Button type="button" variant="outline" className="w-full" onClick={() => router.push(routes.sellerPaymentMethod())}>
                      + Add new account
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label htmlFor="amt">Amount</Label>
                    <Button type="button" variant="ghost" size="sm" className="h-8 text-xs" onClick={() => setAmountStr(String(Math.floor(available)))}>
                      Withdraw all
                    </Button>
                  </div>
                  <Input
                    id="amt"
                    inputMode="numeric"
                    value={amountStr}
                    onChange={(e) => setAmountStr(e.target.value.replace(/[^\d]/g, ''))}
                    placeholder="0"
                  />
                </div>

                <div className="rounded-xl bg-muted/50 p-4 text-sm space-y-1">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Platform fee</span>
                    <span>{formatTZS(platformFee)}</span>
                  </div>
                  <div className="flex justify-between font-semibold">
                    <span>You will receive</span>
                    <span>{formatTZS(receive)}</span>
                  </div>
                </div>

                <Button
                  className="w-full h-12 text-base"
                  disabled={submitting || loading || available <= 0 || amountNum <= 0}
                  onClick={() => void submit()}
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      Working…
                    </>
                  ) : (
                    <>Withdraw {formatTZS(amountNum || 0)}</>
                  )}
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
