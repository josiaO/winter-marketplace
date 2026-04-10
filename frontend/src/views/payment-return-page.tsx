'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useUIStore } from '@/store';
import { api } from '@/lib/api-client';
import { ApiClientError } from '@/types/api';
import { toast } from 'sonner';

const PENDING_REF_KEY = 'sd_pending_txn_ref';

function resolveTransactionReference(
  viewRef: string | null | undefined,
): string | null {
  if (viewRef && String(viewRef).trim()) return String(viewRef).trim();
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    const q =
      params.get('transaction_reference') ||
      params.get('ref') ||
      params.get('reference');
    if (q?.trim()) return q.trim();
    try {
      const s = sessionStorage.getItem(PENDING_REF_KEY);
      if (s?.trim()) return s.trim();
    } catch {
      /* ignore */
    }
  }
  return null;
}

export function PaymentReturnPage() {
  const { currentView, navigate } = useUIStore();
  const viewRef =
    currentView.view === 'payment-return'
      ? (currentView as { reference?: string }).reference
      : undefined;

  const [status, setStatus] = useState<'loading' | 'success' | 'error'>(
    'loading',
  );
  const [message, setMessage] = useState('Confirming your payment with the server…');
  const [orderId, setOrderId] = useState<string | null>(null);
  const [txnRef, setTxnRef] = useState<string | null>(null);

  const runConfirm = useCallback(async (ref: string, signal?: { cancelled: boolean }) => {
    setStatus('loading');
    setMessage('Confirming your payment with the server…');
    try {
      const res = await api.commerce.confirmPaymentReturn({
        transaction_reference: ref,
      });
      if (signal?.cancelled) return;
      const linked = res.transaction?.linked_order_id;
      if (linked != null) {
        setOrderId(String(linked));
      }
      try {
        sessionStorage.removeItem(PENDING_REF_KEY);
      } catch {
        /* ignore */
      }
      setStatus('success');
      setMessage(
        'Payment verified. Your order will update as the marketplace processes it.',
      );
    } catch (err: unknown) {
      if (signal?.cancelled) return;
      let msg =
        'Payment confirmation failed. If you were charged, keep this page and try again or contact support.';
      if (err instanceof ApiClientError) {
        msg = err.detail || err.message || msg;
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setStatus('error');
      setMessage(msg);
      toast.error(msg);
    }
  }, []);

  useEffect(() => {
    const ref = resolveTransactionReference(viewRef);
    setTxnRef(ref);
    if (!ref) {
      setStatus('error');
      setMessage(
        'No transaction reference found. Open this page from the payment return link or your orders.',
      );
      return;
    }
    const signal = { cancelled: false };
    void runConfirm(ref, signal);
    return () => {
      signal.cancelled = true;
    };
  }, [viewRef, runConfirm]);

  const handleRetry = () => {
    if (txnRef) void runConfirm(txnRef);
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md"
      >
        <Card className="border-0 shadow-xl shadow-black/5">
          <CardContent className="p-8 text-center space-y-6">
            {status === 'loading' && (
              <motion.div
                initial={{ scale: 0.8 }}
                animate={{ scale: 1 }}
                className="flex flex-col items-center space-y-4"
              >
                <div className="w-20 h-20 bg-emerald-50 dark:bg-emerald-900/30 rounded-full flex items-center justify-center">
                  <Loader2 className="w-10 h-10 text-emerald-600 animate-spin" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-foreground">
                    Verifying payment
                  </h2>
                  <p className="text-sm text-muted-foreground mt-2">{message}</p>
                </div>
              </motion.div>
            )}

            {status === 'success' && (
              <motion.div
                initial={{ scale: 0.8 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 200, damping: 15 }}
                className="flex flex-col items-center space-y-4"
              >
                <div className="w-20 h-20 bg-emerald-50 dark:bg-emerald-900/30 rounded-full flex items-center justify-center">
                  <CheckCircle className="w-10 h-10 text-emerald-600" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-foreground">
                    Payment verified
                  </h2>
                  <p className="text-sm text-muted-foreground mt-2">{message}</p>
                </div>
              </motion.div>
            )}

            {status === 'error' && (
              <motion.div
                initial={{ scale: 0.8 }}
                animate={{ scale: 1 }}
                className="flex flex-col items-center space-y-4"
              >
                <div className="w-20 h-20 bg-red-50 dark:bg-red-900/30 rounded-full flex items-center justify-center">
                  <AlertCircle className="w-10 h-10 text-red-600" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-foreground">
                    Could not confirm payment
                  </h2>
                  <p className="text-sm text-muted-foreground mt-2">{message}</p>
                </div>
              </motion.div>
            )}

            <div className="flex flex-col gap-2 pt-2">
              {status === 'error' && txnRef && (
                <Button className="w-full rounded-xl" onClick={handleRetry}>
                  Try again
                </Button>
              )}
              {status !== 'loading' && (
                <>
                  {orderId && (
                    <Button
                      className="w-full rounded-xl"
                      onClick={() =>
                        navigate({ view: 'order-detail', id: orderId })
                      }
                    >
                      View order
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    className="w-full rounded-xl"
                    onClick={() => navigate({ view: 'orders' })}
                  >
                    View all orders
                  </Button>
                </>
              )}
              <Button
                variant="ghost"
                className="w-full rounded-xl text-sm"
                onClick={() => navigate({ view: 'home' })}
              >
                Back to home
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
