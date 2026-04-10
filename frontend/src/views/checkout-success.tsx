'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Package, MapPin, ArrowRight, ClipboardList } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { useUIStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, formatDate, orderNumberLabel, orderTotalAmount } from '@/lib/helpers';
import type { Order } from '@/types/api';

// Confetti particles
function Confetti() {
  const particles = Array.from({ length: 30 });
  const colors = ['#10b981', '#f59e0b', '#ef4444', '#3b82f6', '#8b5cf6', '#ec4899'];
  return (
    <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
      {particles.map((_, i) => {
        const left = Math.random() * 100;
        const delay = Math.random() * 0.5;
        const duration = 2 + Math.random() * 2;
        const color = colors[i % colors.length];
        const size = 6 + Math.random() * 8;
        return (
          <motion.div
            key={i}
            initial={{ y: -20, x: 0, opacity: 1, rotate: 0 }}
            animate={{ y: '100vh', x: (Math.random() - 0.5) * 200, opacity: 0, rotate: 360 }}
            transition={{ duration, delay, ease: 'easeOut' }}
            className="absolute"
            style={{
              left: `${left}%`,
              top: '-10px',
              width: size,
              height: size,
              backgroundColor: color,
              borderRadius: Math.random() > 0.5 ? '50%' : '2px',
            }}
          />
        );
      })}
    </div>
  );
}

export function CheckoutSuccessPage() {
  const { currentView, navigate } = useUIStore();
  const orderId = currentView.view === 'checkout-success' ? currentView.orderId : '';
  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setIsLoading] = useState(!!orderId);

  useEffect(() => {
    if (!orderId) return;
    let cancelled = false;
    api.commerce.orderDetail(orderId)
      .then((data) => {
        if (!cancelled) setOrder(data);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => { cancelled = true; };
  }, [orderId]);

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="space-y-6">
          <Skeleton className="h-20 w-20 rounded-full mx-auto" />
          <Skeleton className="h-8 w-48 mx-auto" />
          <Skeleton className="h-40 rounded-2xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-16">
      <Confetti />
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="space-y-6"
      >
        {/* Success Icon */}
        <div className="text-center">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: 'spring', stiffness: 200, damping: 15 }}
            className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-green-100 dark:bg-green-900/30 mb-4"
          >
            <CheckCircle2 className="w-10 h-10 text-green-600 dark:text-green-400" />
          </motion.div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-2">
            Order Confirmed!
          </h1>
          <p className="text-muted-foreground">
            Thank you for your purchase. Your order has been placed successfully.
          </p>
        </div>

        {/* Order Details */}
        <Card>
          <CardContent className="pt-6 space-y-4">
            <div className="flex items-center gap-3">
              <Package className="w-5 h-5 text-muted-foreground" />
              <h3 className="font-semibold text-foreground">Order Details</h3>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-muted-foreground">Order Number</span>
                <p className="font-medium font-mono">{order ? orderNumberLabel(order as any) : 'N/A'}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Total Amount</span>
                <p className="font-semibold text-green-600 dark:text-green-400">
                  {order ? formatTZS(orderTotalAmount(order as any)) : 'N/A'}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground">Order Date</span>
                <p className="font-medium">{order ? formatDate(order.created_at) : 'N/A'}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Items</span>
                <p className="font-medium">{order?.items.length || 0} {order?.items.length === 1 ? 'item' : 'items'}</p>
              </div>
            </div>

            <Separator />

            {/* Shipping Info */}
            <div>
              <div className="flex items-center gap-2 mb-2">
                <MapPin className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-medium text-muted-foreground">Shipping Address</span>
              </div>
              <p className="text-sm text-foreground">{order?.shipping_address || 'N/A'}</p>
            </div>

            <Separator />

            {/* Estimated Delivery */}
            <div className="p-3 rounded-xl bg-muted/50 border">
              <p className="text-sm font-medium text-foreground">
                {order?.shipping_method === 'express'
                  ? '📦 Estimated Delivery: 1-2 business days'
                  : '📦 Estimated Delivery: 5-7 business days'}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                You&apos;ll receive updates on your order status.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3">
          <Button
            className="flex-1 rounded-xl h-12 text-base font-semibold"
            onClick={() => navigate({ view: 'orders' })}
          >
            <ClipboardList className="w-5 h-5 mr-2" />
            View My Orders
          </Button>
          <Button
            variant="outline"
            className="flex-1 rounded-xl h-12 text-base font-semibold"
            onClick={() => navigate({ view: 'home' })}
          >
            Continue Shopping
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </motion.div>
    </div>
  );
}
