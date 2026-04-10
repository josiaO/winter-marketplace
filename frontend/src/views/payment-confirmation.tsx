'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { CreditCard, Loader2, Smartphone, Package } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { api } from '@/lib/api-client';
import { formatTZS, orderNumberLabel, orderTotalAmount } from '@/lib/helpers';
import { toast } from 'sonner';
import {
  escrowFundsSecured,
  type OrderWithEscrow,
} from '@/lib/marketplace-order-payment';

const PENDING_REF_KEY = 'sd_pending_txn_ref';

export function PaymentConfirmationPage({ orderId }: { orderId: string }) {
  const router = useRouter();

  const [order, setOrder] = useState<OrderWithEscrow | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPaying, setIsPaying] = useState(false);

  useEffect(() => {
    if (!orderId) return;
    setIsLoading(true);
    api.commerce
      .orderDetail(orderId)
      .then((data) => setOrder(data as OrderWithEscrow))
      .catch(() => toast.error('Failed to load order details'))
      .finally(() => setIsLoading(false));
  }, [orderId]);

  const handlePayNow = async () => {
    if (!order) return;
    setIsPaying(true);
    try {
      const origin =
        typeof window !== 'undefined' ? window.location.origin : '';
      const res = await api.commerce.initiatePayment(order.id, {
        payment_method: order.payment_method,
        payment_channel: order.payment_channel || undefined,
        redirect_url: origin ? `${origin}/checkout/payment-return` : undefined,
        cancel_url: origin ? `${origin}/checkout/payment-return` : undefined,
      });
      if (res.payment_url) {
        if (res.transaction_reference && typeof sessionStorage !== 'undefined') {
          try {
            sessionStorage.setItem(
              PENDING_REF_KEY,
              res.transaction_reference,
            );
          } catch {
            /* ignore */
          }
        }
        window.location.assign(res.payment_url);
        return;
      }
      toast.error(res.error || 'Could not start payment with the provider.');
    } catch {
      toast.error('Failed to initiate payment');
    } finally {
      setIsPaying(false);
    }
  };

  const getPaymentMethodLabel = (method: string, channel: string | null) => {
    if (channel === 'tigo_pesa') return 'Tigo Pesa';
    if (channel === 'm_pesa') return 'M-Pesa';
    if (channel === 'airtel_money') return 'Airtel Money';
    if (channel === 'halopesa') return 'Halopesa';
    if (channel === 'azam_pay') return 'Azam Pay';
    if (method === 'mobile_money') return 'Mobile Money';
    if (method === 'card') return 'Card';
    return method;
  };

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="space-y-6">
          <Skeleton className="h-8 w-48 mx-auto" />
          <Skeleton className="h-40 rounded-2xl" />
          <Skeleton className="h-12 rounded-xl" />
        </div>
      </div>
    );
  }

  if (!order) return null;

  const total = orderTotalAmount(order);
  const secured = escrowFundsSecured(order);

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="space-y-6"
      >
        <div className="text-center">
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-2">
            {secured ? 'Payment secured' : 'Complete your payment'}
          </h1>
          <p className="text-sm text-muted-foreground">
            {secured
              ? 'Funds are held in escrow according to your order state.'
              : 'You will be sent to the payment provider. Confirmation always runs on the server — do not trust success flags in the URL alone.'}
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Package className="w-4 h-4" />
              Order details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Order</span>
              <span className="font-medium font-mono">
                {orderNumberLabel(order)}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Amount</span>
              <span className="font-semibold text-green-600 dark:text-green-400">
                {formatTZS(total)}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Items</span>
              <span className="font-medium">
                {order.items.length}{' '}
                {order.items.length === 1 ? 'item' : 'items'}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Payment method</span>
              <span className="font-medium flex items-center gap-1">
                <Smartphone className="w-3.5 h-3.5" />
                {getPaymentMethodLabel(
                  order.payment_method,
                  order.payment_channel,
                )}
              </span>
            </div>
          </CardContent>
        </Card>

        {secured ? (
          <Button
            className="w-full h-12 rounded-xl text-base font-semibold"
            size="lg"
            onClick={() =>
              router.push(routes.order(String(order.id)))
            }
          >
            View order
          </Button>
        ) : (
          <Button
            className="w-full h-12 rounded-xl text-base font-semibold"
            size="lg"
            onClick={handlePayNow}
            disabled={isPaying}
          >
            {isPaying ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                Starting payment…
              </>
            ) : (
              <>
                <CreditCard className="w-5 h-5 mr-2" />
                Pay {formatTZS(total)}
              </>
            )}
          </Button>
        )}
      </motion.div>
    </div>
  );
}
