'use client';

import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import {
  Package,
  MapPin,
  Phone,
  Truck,
  CreditCard,
  ChevronLeft,
  CheckCircle2,
  XCircle,
  Star,
  ShieldCheck,
  Clock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { OrderStatusBadge } from '@/components/smartdalali/order-status-badge';
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import {
  formatTZS,
  formatDate,
  formatDateTime,
  getStatusColor,
  getStatusLabel,
  orderTotalAmount,
  orderNumberLabel,
} from '@/lib/helpers';
import { toast } from 'sonner';
import type { Order, OrderStatus } from '@/types/api';

const STATUS_STEPS: OrderStatus[] = [
  'pending',
  'confirmed',
  'processing',
  'shipped',
  'delivered',
];

function StatusTimeline({ order }: { order: Order }) {
  const currentStepIndex = STATUS_STEPS.indexOf(order.status as OrderStatus);

  return (
    <div className="flex items-center gap-1 overflow-x-auto py-2">
      {STATUS_STEPS.map((step, index) => {
        const isCompleted = index < currentStepIndex;
        const isActive = index === currentStepIndex;
        const isCancelled = order.status === 'cancelled';

        if (isCancelled && index > STATUS_STEPS.indexOf(order.status as OrderStatus)) {
          return null;
        }

        return (
          <div key={step} className="flex items-center">
            <div className="flex flex-col items-center min-w-[60px]">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-all ${
                  isCompleted
                    ? 'bg-green-500 border-green-500 text-white'
                    : isActive
                      ? 'bg-primary border-primary text-primary-foreground'
                      : 'bg-background border-muted-foreground/30 text-muted-foreground'
                }`}
              >
                {isCompleted ? <CheckCircle2 className="w-4 h-4" /> : index + 1}
              </div>
              <span
                className={`text-[10px] mt-1 font-medium text-center ${
                  isActive ? 'text-primary' : 'text-muted-foreground'
                }`}
              >
                {getStatusLabel(step)}
              </span>
              {order.status === step && (
                <span className="text-[9px] text-muted-foreground">
                  {formatDateTime(order.created_at)}
                </span>
              )}
            </div>
            {index < STATUS_STEPS.length - 1 && (
              <div
                className={`w-8 sm:w-12 h-0.5 mx-0.5 transition-all ${
                  index < currentStepIndex ? 'bg-green-500' : 'bg-muted-foreground/20'
                }`}
              />
            )}
          </div>
        );
      })}
      {order.status === 'cancelled' && (
        <>
          <div className="w-8 sm:w-12 h-0.5 bg-muted-foreground/20 mx-0.5" />
          <div className="flex flex-col items-center min-w-[60px]">
            <div className="w-7 h-7 rounded-full flex items-center justify-center bg-red-500 border-red-500 text-white">
              <XCircle className="w-4 h-4" />
            </div>
            <span className="text-[10px] mt-1 font-medium text-red-500 text-center">Cancelled</span>
          </div>
        </>
      )}
    </div>
  );
}

export function OrderDetailPage() {
  const { currentView, navigate } = useUIStore();
  const { isAuthenticated } = useAuthStore();
  const orderId = currentView.view === 'order-detail' ? currentView.id : '';

  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isDelivering, setIsDelivering] = useState(false);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('');

  const fetchOrder = useCallback(async () => {
    if (!orderId) return;
    setIsLoading(true);
    try {
      const data = await api.commerce.orderDetail(orderId);
      setOrder(data);
    } catch {
      toast.error('Failed to load order');
      navigate({ view: 'orders' });
    } finally {
      setIsLoading(false);
    }
  }, [orderId, navigate]);

  useEffect(() => {
    fetchOrder();
  }, [fetchOrder]);

  const handleCancelOrder = async () => {
    if (!order) return;
    setIsCancelling(true);
    try {
      await api.commerce.cancelOrderAsBuyer(order.id);
      if (cancelReason.trim()) {
        /* Buyer reason is not persisted on this PATCH; optional future endpoint. */
      }
      toast.success('Order cancelled successfully');
      setCancelDialogOpen(false);
      fetchOrder();
    } catch {
      toast.error('Failed to cancel order');
    } finally {
      setIsCancelling(false);
    }
  };

  const handleConfirmDelivery = async () => {
    if (!order) return;
    setIsDelivering(true);
    try {
      await api.commerce.confirmReceipt(order.id);
      toast.success('Delivery confirmed! Thank you.');
      fetchOrder();
    } catch {
      toast.error('Failed to confirm delivery');
    } finally {
      setIsDelivering(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-4 w-48 mb-4" />
        <Skeleton className="h-8 w-40 mb-6" />
        <Skeleton className="h-24 rounded-xl mb-6" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-20 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </div>
    );
  }

  if (!order) return null;

  const sellerName = order.seller
    ? [order.seller.first_name, order.seller.last_name].filter(Boolean).join(' ') || order.seller.username
    : 'Unknown';

  const paymentMethodLabel = (() => {
    if (order.payment_channel === 'tigo_pesa') return 'Tigo Pesa';
    if (order.payment_channel === 'm_pesa') return 'M-Pesa';
    if (order.payment_channel === 'airtel_money') return 'Airtel Money';
    if (order.payment_channel === 'halopesa') return 'Halopesa';
    if (order.payment_channel === 'azam_pay') return 'Azam Pay';
    if (order.payment_method === 'mobile_money') return 'Mobile Money';
    if (order.payment_method === 'bank_transfer') return 'Bank Transfer';
    if (order.payment_method === 'cash_on_delivery') return 'Cash on Delivery';
    return order.payment_method;
  })();

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Breadcrumb */}
      <Breadcrumb className="mb-4">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink
              className="cursor-pointer text-sm"
              onClick={() => navigate({ view: 'orders' })}
            >
              My Orders
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage className="text-sm font-medium">
              Order #{orderNumberLabel(order)}
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="space-y-6"
      >
        {/* Order Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
              Order #{orderNumberLabel(order)}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Placed on {formatDate(order.created_at)}
            </p>
          </div>
          <OrderStatusBadge status={order.status} className="text-sm px-3 py-1" />
        </div>

        {/* Status Timeline */}
        <Card>
          <CardContent className="pt-6">
            <h3 className="text-sm font-semibold text-foreground mb-3">Order Status</h3>
            <StatusTimeline order={order} />
            {order.tracking_number && (
              <div className="mt-3 p-2 bg-muted/50 rounded-lg text-xs">
                <span className="text-muted-foreground">Tracking: </span>
                <span className="font-mono font-medium">{order.tracking_number}</span>
              </div>
            )}
            {order.dispute && (
              <div className="mt-3 p-2 bg-orange-50 dark:bg-orange-900/20 rounded-lg text-xs text-orange-600 dark:text-orange-400">
                Dispute: {typeof order.dispute === 'object' && order.dispute !== null && 'reason' in order.dispute
                  ? String(order.dispute.reason)
                  : 'Open'}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Action Buttons */}
        {(order.status === 'pending' || order.status === 'confirmed') && (
          <Button
            variant="destructive"
            className="rounded-xl"
            onClick={() => setCancelDialogOpen(true)}
          >
            <XCircle className="w-4 h-4 mr-2" />
            Cancel Order
          </Button>
        )}
        {order.status === 'shipped' && (
          <Button
            className="rounded-xl bg-green-600 hover:bg-green-700"
            onClick={handleConfirmDelivery}
            disabled={isDelivering}
          >
            {isDelivering ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                Confirming...
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4 mr-2" />
                Confirm Delivery
              </>
            )}
          </Button>
        )}
        {order.status === 'delivered' && (
          <Button
            variant="outline"
            className="rounded-xl"
            onClick={() => navigate({ view: 'product', id: String(order.items[0]?.listing?.id || '') })}
          >
            <Star className="w-4 h-4 mr-2" />
            Leave a Review
          </Button>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Items List */}
          <div className="lg:col-span-2 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Package className="w-4 h-4" />
                  Items ({order.items.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {order.items.map((item) => (
                  <div
                    key={item.id}
                    className="flex gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors cursor-pointer"
                    onClick={() => navigate({ view: 'product', id: String(item.listing?.id || '') })}
                  >
                    <div className="relative w-14 h-14 sm:w-16 sm:h-16 rounded-lg overflow-hidden bg-muted flex-shrink-0">
                      {item.listing_image ? (
                        <Image
                          src={item.listing_image}
                          alt={item.listing_title}
                          fill
                          className="object-cover"
                          sizes="64px"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <Package className="w-5 h-5 text-muted-foreground/30" />
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground line-clamp-1">
                        {item.listing_title}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatTZS(item.listing_price)} × {item.quantity}
                      </p>
                    </div>
                    <span className="text-sm font-semibold flex-shrink-0">
                      {formatTZS(item.total)}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          {/* Order Summary Sidebar */}
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Order Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Subtotal</span>
                  <span className="font-medium">{formatTZS(order.subtotal)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Shipping</span>
                  <span className="font-medium">{formatTZS(order.shipping_cost)}</span>
                </div>
                <Separator />
                <div className="flex justify-between">
                  <span className="font-semibold">Total</span>
                  <span className="text-lg font-bold text-foreground">
                    {formatTZS(orderTotalAmount(order))}
                  </span>
                </div>
              </CardContent>
            </Card>

            {/* Shipping Info */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Truck className="w-4 h-4" />
                  Shipping
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex items-start gap-2">
                  <MapPin className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                  <span>{order.shipping_address}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Phone className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  <span>{order.shipping_phone}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Truck className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  <span className="capitalize">{order.shipping_method}</span>
                </div>
              </CardContent>
            </Card>

            {/* Payment Info */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <CreditCard className="w-4 h-4" />
                  Payment
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Method</span>
                  <span className="font-medium">{paymentMethodLabel}</span>
                </div>
                {order.transaction_reference && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Reference</span>
                    <span className="font-mono text-xs">{order.transaction_reference}</span>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Seller Info */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4" />
                  Seller
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-medium">
                    {order.seller?.seller_profile?.business_name || sellerName}
                  </span>
                  {order.seller?.is_verified && (
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </motion.div>

      {/* Cancel Dialog */}
      <Dialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel Order</DialogTitle>
            <DialogDescription>
              Are you sure you want to cancel this order? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="cancel-reason">Reason for cancellation</Label>
            <Textarea
              id="cancel-reason"
              placeholder="Please provide a reason..."
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelDialogOpen(false)}>
              Keep Order
            </Button>
            <Button
              variant="destructive"
              onClick={handleCancelOrder}
              disabled={isCancelling}
            >
              {isCancelling ? 'Cancelling...' : 'Cancel Order'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
