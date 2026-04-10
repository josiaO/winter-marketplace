'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Truck,
  Package,
  Clock,
  CheckCircle2,
  XCircle,
  MapPin,
  Phone,
  Loader2,
  PackageOpen,
  Send,
  ImageOff,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useAuthStore } from '@/store';
import { canAccessSellerPortal } from '@/lib/auth-roles';
import { api } from '@/lib/api-client';
import {
  formatTZS,
  formatDate,
  formatDateTime,
  getStatusColor,
  getStatusLabel,
  orderNumberLabel,
  orderTotalAmount,
  commerceOrderItemTitle,
  commerceOrderItemImage,
  commerceOrderItemUnitPrice,
  commerceOrderItemLineTotal,
} from '@/lib/helpers';
import { ApiClientError } from '@/types/api';
import { EmptyState } from '@/components/smartdalali/empty-state';
import type { Order, PaginatedResponse } from '@/types/api';

const STATUS_TABS = [
  { value: 'all', label: 'All', icon: Package },
  { value: 'pending', label: 'Pending', icon: Clock },
  { value: 'confirmed', label: 'Confirmed', icon: CheckCircle2 },
  { value: 'processing', label: 'Processing', icon: Package },
  { value: 'shipped', label: 'Shipped', icon: Truck },
  { value: 'arrived', label: 'Arrived', icon: MapPin },
  { value: 'delivered', label: 'Delivered', icon: CheckCircle2 },
  { value: 'cancelled', label: 'Cancelled', icon: XCircle },
];

export function SellerOrdersPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');
  const [expandedOrder, setExpandedOrder] = useState<number | null>(null);
  const [shipDialogOrder, setShipDialogOrder] = useState<Order | null>(null);
  const [trackingNumber, setTrackingNumber] = useState('');
  const [carrier, setCarrier] = useState('');
  const [shipmentVideo, setShipmentVideo] = useState<File | null>(null);
  const [shipmentImages, setShipmentImages] = useState<File[]>([]);
  const [isShipping, setIsShipping] = useState(false);

  const loadOrders = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.commerce.orders({ role: 'seller' });
      const items =
        (data as PaginatedResponse<Order>).results ??
        (Array.isArray(data) ? data : []);
      setOrders(items as Order[]);
    } catch {
      toast.error('Failed to load orders.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push(routes.login());
      return;
    }
    if (!canAccessSellerPortal(user)) {
      toast.error('You must be a seller to view orders.');
      router.push(routes.sellerRegister());
      return;
    }

    void loadOrders();
  }, [isAuthenticated, user, navigate, loadOrders]);

  const filteredOrders = useMemo(() => {
    if (activeTab === 'all') return orders;
    return orders.filter((o) => o.status === activeTab);
  }, [orders, activeTab]);

  const orderCounts = useMemo(() => {
    const counts: Record<string, number> = { all: orders.length };
    orders.forEach((o) => {
      counts[o.status] = (counts[o.status] || 0) + 1;
    });
    return counts;
  }, [orders]);

  const handleShipOrder = async () => {
    if (!shipDialogOrder || !trackingNumber.trim()) return;
    setIsShipping(true);
    try {
      await api.commerce.shipOrder(shipDialogOrder.id, {
        tracking_number: trackingNumber.trim(),
        carrier: carrier.trim() || undefined,
        shipment_video: shipmentVideo || undefined,
        shipment_images: shipmentImages.length > 0 ? shipmentImages : undefined,
      });
      toast.success('Order marked as shipped!');
      setShipDialogOrder(null);
      setTrackingNumber('');
      setCarrier('');
      setShipmentVideo(null);
      setShipmentImages([]);
      await loadOrders();
    } catch (err: unknown) {
      const message =
        err instanceof ApiClientError
          ? err.detail || err.message
          : err instanceof Error
            ? err.message
            : 'Failed to ship order.';
      toast.error(message);
    } finally {
      setIsShipping(false);
    }
  };

  const handleMarkArrived = async (orderId: number) => {
    setIsLoading(true);
    try {
      await api.commerce.markArrived(orderId);
      toast.success('Order marked as arrived at pickup point!');
      await loadOrders();
    } catch (err: unknown) {
      const message =
        err instanceof ApiClientError
          ? err.detail || err.message
          : 'Failed to mark as arrived.';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const canShip = (order: Order) =>
    ['pending', 'confirmed', 'processing'].includes(order.status);

  const canMarkArrived = (order: Order) => order.status === 'shipped';

  if (!isAuthenticated || !user) return null;

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground">Seller Orders</h1>
          <p className="text-muted-foreground mt-1">
            Manage and track your customer orders
          </p>
        </motion.div>

        {/* Order Count Summary */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="flex flex-wrap gap-2"
        >
          {STATUS_TABS.map((tab) => {
            const count = orderCounts[tab.value] || 0;
            return (
              <Badge
                key={tab.value}
                variant="outline"
                className="px-3 py-1.5 text-xs font-medium"
              >
                <tab.icon className="w-3 h-3 mr-1" />
                {tab.label}: {count}
              </Badge>
            );
          })}
        </motion.div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="w-full justify-start bg-muted/50 p-1 h-auto flex-wrap gap-1">
            {STATUS_TABS.map((tab) => (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className="gap-1.5 text-xs sm:text-sm data-[state=active]:bg-background data-[state=active]:shadow-sm rounded-lg px-3 py-2"
              >
                <tab.icon className="w-3.5 h-3.5 hidden sm:block" />
                {tab.label}
                {(orderCounts[tab.value] || 0) > 0 && (
                  <span className="ml-1 text-[10px] bg-muted rounded-full px-1.5 py-0.5 font-semibold">
                    {orderCounts[tab.value]}
                  </span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>

          {STATUS_TABS.map((tab) => (
            <TabsContent key={tab.value} value={tab.value} className="mt-4">
              {isLoading ? (
                <div className="space-y-3">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-40 w-full" />
                  ))}
                </div>
              ) : filteredOrders.length === 0 ? (
                <EmptyState
                  icon={PackageOpen}
                  title={`No ${activeTab !== 'all' ? tab.label.toLowerCase() : ''} orders`}
                  description={
                    tab.value === 'all'
                      ? 'Orders will appear here when customers purchase your products.'
                      : `You don't have any ${tab.label.toLowerCase()} orders at the moment.`
                  }
                />
              ) : (
                <div className="space-y-3">
                  <AnimatePresence mode="popLayout">
                    {filteredOrders.map((order) => {
                      const isExpanded = expandedOrder === order.id;
                      const buyerName = order.buyer
                        ? [order.buyer.first_name, order.buyer.last_name].filter(Boolean).join(' ') || order.buyer.username
                        : 'Unknown Buyer';
                      return (
                        <motion.div
                          key={order.id}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -10 }}
                          layout
                        >
                          <Card className="border-0 shadow-md shadow-black/5 hover:shadow-lg transition-shadow overflow-hidden">
                            {/* Order Header */}
                            <div
                              className="p-4 sm:p-5 cursor-pointer"
                              onClick={() =>
                                setExpandedOrder(isExpanded ? null : order.id)
                              }
                            >
                              <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 flex-wrap">
                                    <h3 className="text-sm font-semibold text-foreground">
                                      #
                                      {orderNumberLabel(order).replace(
                                        /^ORD-0+/,
                                        '',
                                      ).slice(-8) || order.id}
                                    </h3>
                                    <Badge
                                      variant="secondary"
                                      className={`text-xs ${getStatusColor(order.status)}`}
                                    >
                                      {getStatusLabel(order.status)}
                                    </Badge>
                                  </div>
                                  <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
                                    <span className="flex items-center gap-1">
                                      <Package className="w-3 h-3" />
                                      {buyerName}
                                    </span>
                                    <span>
                                      {formatDate(order.created_at)}
                                    </span>
                                    <span className="font-semibold text-foreground">
                                      {formatTZS(orderTotalAmount(order))}
                                    </span>
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  {canShip(order) && (
                                    <Button
                                      size="sm"
                                      className="gap-1.5 text-xs shrink-0"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setShipDialogOrder(order);
                                      }}
                                    >
                                      <Send className="w-3.5 h-3.5" />
                                      Mark Shipped
                                    </Button>
                                  )}
                                  {canMarkArrived(order) && (
                                    <Button
                                      size="sm"
                                      variant="secondary"
                                      className="gap-1.5 text-xs shrink-0 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border-indigo-200"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleMarkArrived(order.id);
                                      }}
                                    >
                                      <MapPin className="w-3.5 h-3.5" />
                                      Mark Arrived
                                    </Button>
                                  )}
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8 shrink-0"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setExpandedOrder(isExpanded ? null : order.id);
                                    }}
                                  >
                                    {isExpanded ? (
                                      <ChevronUp className="w-4 h-4" />
                                    ) : (
                                      <ChevronDown className="w-4 h-4" />
                                    )}
                                  </Button>
                                </div>
                              </div>
                            </div>

                            {/* Expanded Details */}
                            <AnimatePresence>
                              {isExpanded && (
                                <motion.div
                                  initial={{ height: 0, opacity: 0 }}
                                  animate={{ height: 'auto', opacity: 1 }}
                                  exit={{ height: 0, opacity: 0 }}
                                  transition={{ duration: 0.2 }}
                                  className="overflow-hidden"
                                >
                                  <Separator />
                                  <div className="p-4 sm:p-5 space-y-4 bg-muted/20">
                                    {/* Order Items */}
                                    <div>
                                      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                        Items
                                      </h4>
                                      <div className="space-y-2">
                                        {order.items.map((item) => {
                                          const img = commerceOrderItemImage(item);
                                          return (
                                          <div
                                            key={item.id}
                                            className="flex items-center gap-3 bg-background rounded-lg p-2.5"
                                          >
                                            <div className="w-12 h-12 rounded-lg bg-muted overflow-hidden shrink-0">
                                              {img ? (
                                                <img
                                                  src={img}
                                                  alt={commerceOrderItemTitle(item)}
                                                  className="w-full h-full object-cover"
                                                />
                                              ) : (
                                                <div className="w-full h-full flex items-center justify-center">
                                                  <ImageOff className="w-4 h-4 text-muted-foreground/40" />
                                                </div>
                                              )}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                              <p className="text-sm font-medium text-foreground truncate">
                                                {commerceOrderItemTitle(item)}
                                              </p>
                                              <p className="text-xs text-muted-foreground">
                                                {formatTZS(commerceOrderItemUnitPrice(item))} x {item.quantity}
                                              </p>
                                            </div>
                                            <span className="text-sm font-semibold text-foreground shrink-0">
                                              {formatTZS(commerceOrderItemLineTotal(item))}
                                            </span>
                                          </div>
                                        );
                                        })}
                                      </div>
                                    </div>

                                    {/* Shipping Info */}
                                    <div>
                                      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                        Shipping Details
                                      </h4>
                                      <div className="bg-background rounded-lg p-3 space-y-2">
                                        <div className="flex items-start gap-2">
                                          <MapPin className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
                                          <p className="text-sm text-foreground">
                                            {order.shipping_address}
                                          </p>
                                        </div>
                                        <div className="flex items-center gap-2">
                                          <Phone className="w-4 h-4 text-muted-foreground shrink-0" />
                                          <p className="text-sm text-foreground">
                                            {order.shipping_phone}
                                          </p>
                                        </div>
                                        {order.tracking_number && (
                                          <div className="flex items-center gap-2">
                                            <Truck className="w-4 h-4 text-muted-foreground shrink-0" />
                                            <p className="text-sm text-foreground">
                                              Tracking: {order.tracking_number}
                                            </p>
                                          </div>
                                        )}
                                      </div>
                                    </div>

                                    {/* Order Totals */}
                                    <div className="flex justify-end">
                                      <div className="text-right space-y-1">
                                        <div className="flex gap-6 text-sm">
                                          <span className="text-muted-foreground">Subtotal</span>
                                          <span className="text-foreground">
                                            {formatTZS(order.subtotal)}
                                          </span>
                                        </div>
                                        <div className="flex gap-6 text-sm">
                                          <span className="text-muted-foreground">Shipping</span>
                                          <span className="text-foreground">
                                            {formatTZS(order.shipping_cost)}
                                          </span>
                                        </div>
                                        <Separator />
                                        <div className="flex gap-6 text-sm font-bold">
                                          <span className="text-foreground">Total</span>
                                          <span className="text-primary">
                                            {formatTZS(orderTotalAmount(order))}
                                          </span>
                                        </div>
                                      </div>
                                    </div>

                                    {/* Timeline */}
                                    <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                                      {order.created_at && (
                                        <span>Created: {formatDateTime(order.created_at)}</span>
                                      )}
                                    </div>
                                  </div>
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </Card>
                        </motion.div>
                      );
                    })}
                  </AnimatePresence>
                </div>
              )}
            </TabsContent>
          ))}
        </Tabs>

        {/* Ship Dialog */}
        <Dialog
          open={!!shipDialogOrder}
          onOpenChange={(open) => {
            if (!open) {
              setShipDialogOrder(null);
              setTrackingNumber('');
              setCarrier('');
              setShipmentVideo(null);
              setShipmentImages([]);
            }
          }}
        >
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Mark Order as Shipped</DialogTitle>
              <DialogDescription>
                Add a tracking number for order #{shipDialogOrder?.order_number.slice(-8)}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="carrier">Carrier / Method</Label>
                  <Input
                    id="carrier"
                    placeholder="e.g. DHL, Bodaboda"
                    value={carrier}
                    onChange={(e) => setCarrier(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="trackingNumber">Tracking Number</Label>
                  <Input
                    id="trackingNumber"
                    placeholder="e.g. TRK123456"
                    value={trackingNumber}
                    onChange={(e) => setTrackingNumber(e.target.value)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Shipment Evidence (Images)</Label>
                <Input
                  type="file"
                  multiple
                  accept="image/*"
                  onChange={(e) => {
                    const files = Array.from(e.target.files || []);
                    setShipmentImages(files);
                  }}
                  className="cursor-pointer"
                />
                <p className="text-[10px] text-muted-foreground">
                  Upload photos of the packaged item and receipt.
                </p>
              </div>

              <div className="space-y-2">
                <Label>Packing Video (Optional)</Label>
                <Input
                  type="file"
                  accept="video/*"
                  onChange={(e) => {
                    const file = e.target.files?.[0] || null;
                    setShipmentVideo(file);
                  }}
                  className="cursor-pointer"
                />
                <p className="text-[10px] text-muted-foreground">
                  A short video of you sealing the package.
                </p>
              </div>
              <div className="rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
                <p className="font-medium text-foreground mb-1">Shipping to:</p>
                <p>{shipDialogOrder?.shipping_address}</p>
                <p>{shipDialogOrder?.shipping_phone}</p>
              </div>
            </div>
            <DialogFooter className="gap-2 sm:gap-0">
              <Button
                variant="outline"
                onClick={() => {
                  setShipDialogOrder(null);
                  setTrackingNumber('');
                  setCarrier('');
                  setShipmentVideo(null);
                  setShipmentImages([]);
                }}
                disabled={isShipping}
              >
                Cancel
              </Button>
              <Button
                onClick={handleShipOrder}
                disabled={isShipping || !trackingNumber.trim()}
                className="gap-2"
              >
                {isShipping ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Shipping...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    Confirm Shipment
                  </>
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
