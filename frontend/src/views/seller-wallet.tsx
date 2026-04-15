'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Wallet, ArrowUpRight, ChevronLeft } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { routes } from '@/lib/routes';
import { api } from '@/lib/api-client';
import { formatTZS } from '@/lib/helpers';
import type { CommerceSellerStats } from '@/types/api';
import { useAuthStore } from '@/store';

export function SellerWalletPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [stats, setStats] = useState<CommerceSellerStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated || !user?.is_seller) return;
    void (async () => {
      try {
        const s = (await api.commerce.sellerStats()) as CommerceSellerStats;
        setStats(s);
      } catch {
        toast.error('Could not load wallet.');
      } finally {
        setLoading(false);
      }
    })();
  }, [isAuthenticated, user]);

  if (!isAuthenticated || !user?.is_seller) return null;

  const available = Math.max(0, stats?.escrow?.available_for_withdrawal ?? 0);
  const held = stats?.escrow?.held ?? 0;

  return (
    <div className="space-y-6 max-w-lg mx-auto">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-4"
      >
        <Button
          variant="outline"
          size="icon"
          className="rounded-full shadow-sm bg-white shrink-0"
          onClick={() => router.push(routes.sellerDashboard())}
        >
          <ChevronLeft className="w-5 h-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Wallet className="w-7 h-7 text-primary" />
            Wallet
          </h1>
          <p className="text-muted-foreground mt-1">Money that is ready for you, and money still in escrow.</p>
        </div>
      </motion.div>

      <Card className="border-0 shadow-lg">
        <CardHeader>
          <CardTitle>Available balance</CardTitle>
          <CardDescription>Released from escrow and ready to withdraw to M-Pesa or your saved payout account.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <Skeleton className="h-12 w-48" />
          ) : (
            <p className="text-3xl font-bold">{formatTZS(available)}</p>
          )}
          <div className="text-sm text-muted-foreground space-y-1">
            <p>In escrow: {loading ? '—' : formatTZS(held)}</p>
          </div>
          <Button className="w-full gap-2 h-12 text-base" disabled={loading || available <= 0} onClick={() => router.push(routes.sellerWalletWithdraw())}>
            Withdraw now
            <ArrowUpRight className="w-4 h-4" />
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
