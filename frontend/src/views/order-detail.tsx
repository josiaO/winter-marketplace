'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import {
  Package,
  MapPin,
  Phone,
  Truck,
  CreditCard,
  Star,
  ShieldCheck,
  MessageSquare,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
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
import { EscrowBuyerProgress } from '@/components/smartdalali/escrow-buyer-progress';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import {
  formatTZS,
  formatDate,
  formatDateTime,
  getStatusLabel,
  orderTotalAmount,
  orderNumberLabel,
  commerceOrderItemTitle,
  commerceOrderItemImage,
  commerceOrderItemUnitPrice,
  commerceOrderItemLineTotal,
} from '@/lib/helpers';
import { buyerShouldSeeOnlinePaymentCta } from '@/lib/marketplace-order-payment';
import { toast } from 'sonner';
import { ApiClientError, type Order, type OrderStatus } from '@/types/api';

const STATUS_STEPS: OrderStatus[] = [
  'pending',
  'confirmed',
  'processing',
  'shipped',
  'arrived',
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

export function OrderDetailPage({ orderId }: { orderId: string }) {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  
  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isDelivering, setIsDelivering] = useState(false);
  const [isMarkingArrived, setIsMarkingArrived] = useState(false);
  const [isDisputing, setIsDisputing] = useState(false);
  
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  
  const [disputeDialogOpen, setDisputeDialogOpen] = useState(false);
  const [disputeCategory, setDisputeCategory] = useState('other');
  const [disputeReason, setDisputeReason] = useState('');
  const [evidenceImages, setEvidenceImages] = useState<File[]>([]);
  const [evidenceVideo, setEvidenceVideo] = useState<File | null>(null);

  // Review states
  const [reviewDialogOpen, setReviewDialogOpen] = useState(false);
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewComment, setReviewComment] = useState('');
  const [reviewPhotos, setReviewPhotos] = useState<File[]>([]);
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  const fetchOrder = useCallback(async () => {
    if (!orderId) return;
    setIsLoading(true);
    try {
      const data = await api.commerce.orderDetail(orderId);
      setOrder(data);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError
          ? err.detail || err.message
          : 'Failed to load order';
      toast.error(msg);
      router.push(routes.orders());
    } finally {
      setIsLoading(false);
    }
  }, [orderId, router]);

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
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError
          ? err.detail || err.message
          : 'Failed to cancel order';
      toast.error(msg);
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
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError
          ? err.detail || err.message
          : 'Failed to confirm delivery';
      toast.error(msg);
    } finally {
      setIsDelivering(false);
    }
  };

  const handleMarkArrived = async () => {
    if (!order) return;
    setIsMarkingArrived(true);
    try {
      await api.commerce.markArrived(order.id);
      toast.success('Order marked as arrived at pickup point!');
      fetchOrder();
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError
          ? err.detail || err.message
          : 'Failed to mark as arrived';
      toast.error(msg);
    } finally {
      setIsMarkingArrived(false);
    }
  };

  const handleOpenDispute = async () => {
    if (!order || !disputeReason.trim()) return;
    setIsDisputing(true);
    try {
      await api.commerce.openDispute(order.id, {
        dispute_category: disputeCategory,
        dispute_reason: disputeReason.trim(),
        evidence_images: evidenceImages.length > 0 ? evidenceImages : undefined,
        evidence_video: evidenceVideo || undefined,
      });
      toast.success('Dispute opened successfully. Support will investigate.');
      setDisputeDialogOpen(false);
      setDisputeReason('');
      setDisputeCategory('other');
      setEvidenceImages([]);
      setEvidenceVideo(null);
      fetchOrder();
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError
          ? err.detail || err.message
          : 'Failed to open dispute';
      toast.error(msg);
    } finally {
      setIsDisputing(false);
    }
  };

  const handleSubmitReview = async () => {
    if (!order) return;
    setIsSubmittingReview(true);
    try {
      await api.commerce.reviewOrder(
        order.id,
        { rating: reviewRating, comment: reviewComment },
        reviewPhotos.length > 0 ? reviewPhotos : undefined,
      );
      toast.success('Review submitted successfully!');
      setReviewDialogOpen(false);
      setReviewPhotos([]);
      setReviewComment('');
      fetchOrder();
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError
          ? err.detail || err.message
          : 'Failed to submit review';
      toast.error(msg);
    } finally {
      setIsSubmittingReview(false);
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
              onClick={() => router.push(routes.orders())}
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
        <EscrowBuyerProgress order={order} />

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row flex-wrap gap-3">
        {buyerShouldSeeOnlinePaymentCta(order) && (
          <Button
            className="rounded-xl bg-emerald-600 hover:bg-emerald-700"
            onClick={() =>
              router.push(routes.checkoutConfirm(String(order.id)))
            }
          >
            <CreditCard className="w-4 h-4 mr-2" />
            Complete payment
          </Button>
        )}
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
        {(order.status === 'delivered' || order.status === 'completed') && (
          <Button
            variant="outline"
            className="rounded-xl border-emerald-500 text-emerald-600 hover:bg-emerald-50"
            onClick={() => setReviewDialogOpen(true)}
            disabled={!!order.review}
          >
            <Star className="w-4 h-4 mr-2" />
            {order.review ? 'Review Submitted' : 'Leave a Review'}
          </Button>
        )}
        
        {/* Buyer: Open Dispute when Arrived */}
        {(order.status === 'arrived' || order.status === 'shipped') && order.buyer?.id === user?.id && (
          <Button
            variant="outline"
            className="rounded-xl border-orange-500 text-orange-600 hover:bg-orange-50"
            onClick={() => setDisputeDialogOpen(true)}
          >
            <ShieldCheck className="w-4 h-4 mr-2" />
            Open Dispute
          </Button>
        )}

        {/* Seller: Mark Arrived when Shipped */}
        {order.status === 'shipped' && order.seller?.id === user?.id && (
          <Button
            className="rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white"
            onClick={handleMarkArrived}
            disabled={isMarkingArrived}
          >
            {isMarkingArrived ? (
              <>
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2" />
                Updating...
              </>
            ) : (
              <>
                <MapPin className="w-4 h-4 mr-2" />
                Mark Arrived at Destination
              </>
            )}
          </Button>
        )}
        </div>

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
                {order.items.map((item) => {
                  const lineImage = commerceOrderItemImage(item);
                  return (
                  <div
                    key={item.id}
                    className="flex gap-3 p-2 rounded-lg hover:bg-muted/50 transition-colors cursor-pointer"
                    onClick={() => router.push(routes.product(String(item.listing?.id || '')))}
                  >
                    <div className="relative w-14 h-14 sm:w-16 sm:h-16 rounded-lg overflow-hidden bg-muted flex-shrink-0">
                      {lineImage ? (
                        <Image
                          src={lineImage}
                          alt={commerceOrderItemTitle(item)}
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
                        {commerceOrderItemTitle(item)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatTZS(commerceOrderItemUnitPrice(item))} × {item.quantity}
                      </p>
                    </div>
                    <span className="text-sm font-semibold flex-shrink-0">
                      {formatTZS(commerceOrderItemLineTotal(item))}
                    </span>
                  </div>
                );
                })}
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
                {buyerShouldSeeOnlinePaymentCta(order) && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full mt-2 rounded-lg"
                    onClick={() =>
                      router.push(routes.checkoutConfirm(String(order.id)))
                    }
                  >
                    <CreditCard className="w-3.5 h-3.5 mr-2" />
                    Pay or retry checkout
                  </Button>
                )}
              </CardContent>
            </Card>

            {/* Seller Info */}
            <Card>
              <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4" />
                  Seller
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 text-xs text-primary hover:text-primary hover:bg-primary/5 rounded-lg"
                  onClick={async () => {
                    const sellerId = order.seller?.id;
                    if (!sellerId) return;
                    try {
                      const conv = await api.communications.startConversation({
                        seller_id: sellerId,
                        order_id: order.id,
                      });
                      router.push(routes.messageThread(String(conv.id)));
                    } catch {
                      toast.error('Failed to start conversation');
                    }
                  }}
                >
                  <MessageSquare className="w-3.5 h-3.5 mr-1" />
                  Message
                </Button>
              </div>
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

      {/* Dispute Dialog */}
      <Dialog open={disputeDialogOpen} onOpenChange={setDisputeDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-orange-600">
              <ShieldCheck className="w-5 h-5" />
              Open a Dispute
            </DialogTitle>
            <DialogDescription>
              We review every dispute with real people and aim to resolve within 7 days.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>What went wrong?</Label>
              <div className="grid grid-cols-1 gap-2">
                {[
                  ['never_arrived', 'Item never arrived'],
                  ['not_as_described', 'Item is different from description'],
                  ['damaged', 'Item arrived damaged'],
                  ['seller_unresponsive', 'Seller is unresponsive'],
                  ['other', 'Other'],
                ].map(([key, title]) => (
                  <button
                    key={key}
                    type="button"
                    className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition ${
                      disputeCategory === key
                        ? 'border-primary bg-primary/5 text-foreground'
                        : 'border-muted-foreground/20 text-muted-foreground hover:text-foreground'
                    }`}
                    onClick={() => setDisputeCategory(key)}
                  >
                    {title}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="dispute-reason">Your explanation</Label>
              <Textarea
                id="dispute-reason"
                placeholder="Share any details that help us resolve this fairly..."
                value={disputeReason}
                onChange={(e) => setDisputeReason(e.target.value)}
                rows={4}
              />
            </div>

            <div className="space-y-2">
              <Label>Evidence Photos</Label>
              <Input
                type="file"
                multiple
                accept="image/*"
                onChange={(e) => setEvidenceImages(Array.from(e.target.files || []))}
                className="cursor-pointer"
              />
            </div>

            <div className="space-y-2">
              <Label>Short Video Evidence (Optional)</Label>
              <Input
                type="file"
                accept="video/*"
                onChange={(e) => setEvidenceVideo(e.target.files?.[0] || null)}
                className="cursor-pointer"
              />
            </div>
            
            <div className="p-3 bg-muted/50 rounded-lg text-xs text-muted-foreground flex gap-2">
              <ShieldCheck className="w-4 h-4 shrink-0 text-orange-500" />
              <p>
                Every dispute is reviewed by a real person. If we rule in your favor,
                your refund is processed within 24 hours.
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDisputeDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              className="bg-orange-600 hover:bg-orange-700 text-white"
              onClick={handleOpenDispute}
              disabled={isDisputing || !disputeReason.trim()}
            >
              {isDisputing ? 'Submitting...' : 'Submit Dispute'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Review Dialog */}
      <Dialog open={reviewDialogOpen} onOpenChange={setReviewDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Star className="w-5 h-5 text-emerald-600 fill-emerald-600" />
              Rate your experience
            </DialogTitle>
            <DialogDescription>
              Share your experience with the seller and the product to help other buyers.
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-2">
            <div className="flex items-center justify-center gap-2 py-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setReviewRating(i + 1)}
                  className="focus:outline-none transition-all hover:scale-110"
                >
                  <Star
                    className={`w-9 h-9 ${
                      i < reviewRating
                        ? 'fill-amber-400 text-amber-400'
                        : 'text-gray-300 dark:text-gray-600'
                    }`}
                  />
                </button>
              ))}
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="review-comment">What did you think?</Label>
              <Textarea
                id="review-comment"
                placeholder="Share more details about the product and seller service..."
                value={reviewComment}
                onChange={(e) => setReviewComment(e.target.value)}
                rows={4}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="review-photos">Attach photos (Optional)</Label>
              <Input
                id="review-photos"
                type="file"
                multiple
                accept="image/*"
                onChange={(e) => setReviewPhotos(Array.from(e.target.files || []))}
                className="cursor-pointer"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setReviewDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              onClick={handleSubmitReview}
              disabled={isSubmittingReview}
            >
              {isSubmittingReview ? 'Submitting...' : 'Submit Review'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
