'use client';

import { useParams, useRouter, usePathname } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useCallback, useEffect, useState } from 'react';
import {
  ArrowLeft,
  CheckCircle2,
  Circle,
  Clock,
  Copy,
  Loader2,
  MapPin,
  MessageCircle,
  Package,
  Phone,
  Send,
  Truck,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer';
import { useAuthStore } from '@/store';
import { canAccessSellerPortal } from '@/lib/auth-roles';
import { api } from '@/lib/api-client';
import {
  formatTZS,
  getRelativeTime,
  orderTotalAmount,
  commerceOrderItemTitle,
  commerceOrderItemImage,
  commerceOrderItemUnitPrice,
  commerceOrderItemLineTotal,
  orderNumberLabel,
} from '@/lib/helpers';
import { ApiClientError } from '@/types/api';
import type { Order } from '@/types/api';

function waLink(phone?: string | null): string {
  const digits = String(phone || '').replace(/\D/g, '');
  if (!digits) return '#';
  const n = digits.startsWith('0') ? `255${digits.slice(1)}` : digits;
  return `https://wa.me/${n}`;
}

const AUTO_CONFIRM_DAYS = 7;

export function SellerOrderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated } = useAuthStore();
  const id = String(params?.id ?? '');
  const disputeFocus = pathname?.endsWith('/dispute') ?? false;

  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [shipOpen, setShipOpen] = useState(false);
  const [trackingNumber, setTrackingNumber] = useState('');
  const [carrier, setCarrier] = useState('');
  const [shipmentVideo, setShipmentVideo] = useState<File | null>(null);
  const [shipmentImages, setShipmentImages] = useState<File[]>([]);
  const [shipping, setShipping] = useState(false);
  const [shipDone, setShipDone] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const o = await api.commerce.orderDetail(id);
      setOrder(o);
    } catch {
      toast.error('Could not load this order.');
      router.push(routes.sellerOrders());
    } finally {
      setLoading(false);
    }
  }, [id, router]);

  useEffect(() => {
    if (isAuthenticated && user && canAccessSellerPortal(user)) {
      void load();
    }
  }, [isAuthenticated, user, load]);

  const copyAddr = () => {
    if (!order?.shipping_address) return;
    void navigator.clipboard.writeText(order.shipping_address);
    toast.success('Address copied');
  };

  const openChat = async () => {
    if (!order) return;
    try {
      const conv = await api.communications.startConversation({
        order_id: order.id,
        user_id: order.buyer?.id,
      });
      router.push(routes.messageThread(String(conv.id)));
    } catch {
      toast.error('Could not open chat. Try Messages.');
      router.push(routes.messages());
    }
  };

  const canShip = order && ['confirmed', 'processing'].includes(order.status);
  const hasEvidence = shipmentImages.length > 0 || !!shipmentVideo;

  const submitShip = async () => {
    if (!order || !hasEvidence) {
      toast.error('Please upload a photo or video of the sealed parcel.');
      return;
    }
    setShipping(true);
    try {
      await api.commerce.shipOrder(order.id, {
        tracking_number: trackingNumber.trim() || 'N/A',
        carrier: carrier.trim() || undefined,
        shipment_video: shipmentVideo || undefined,
        shipment_images: shipmentImages.length > 0 ? shipmentImages : undefined,
      });
      setShipOpen(false);
      setShipDone(true);
      setTrackingNumber('');
      setCarrier('');
      setShipmentVideo(null);
      setShipmentImages([]);
      toast.success('Marked as shipped');
      await load();
    } catch (err: unknown) {
      const message =
        err instanceof ApiClientError
          ? err.detail || err.message
          : err instanceof Error
            ? err.message
            : 'Could not mark shipped.';
      toast.error(message);
    } finally {
      setShipping(false);
    }
  };

  if (!isAuthenticated || !user) return null;

  if (loading || !order) {
    return (
      <div className="space-y-4 max-w-3xl mx-auto">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const sellerId = typeof order.seller === 'object' && order.seller ? order.seller.id : (order.seller as number | undefined);
  if (sellerId != null && sellerId !== user.id && !user.is_staff) {
    toast.error('You do not have access to this order.');
    router.push(routes.sellerOrders());
    return null;
  }

  const placed = Boolean(order.created_at);
  const paid = ['confirmed', 'processing', 'shipped', 'arrived', 'delivered', 'completed'].includes(order.status);
  const shipped = ['shipped', 'arrived', 'delivered', 'completed'].includes(order.status);
  const buyerReceived = ['delivered', 'completed'].includes(order.status);
  const fundsReleased = order.status === 'completed';

  const steps = [
    { key: 'placed', label: 'Order placed', done: placed, at: order.created_at },
    {
      key: 'paid',
      label:
        order.status === 'pending'
          ? 'Awaiting buyer payment'
          : 'Payment received (held in escrow)',
      done: paid,
      at: order.confirmed_at || (paid ? order.updated_at : undefined),
    },
    { key: 'ship', label: 'You ship the item', done: shipped, action: canShip },
    { key: 'recv', label: 'Buyer confirms receipt', done: buyerReceived, at: undefined },
    { key: 'funds', label: 'Funds released to you', done: fundsReleased, at: order.updated_at },
  ];

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-24">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push(routes.sellerOrders())}>
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div>
          <h1 className="text-xl sm:text-2xl font-bold">Order {orderNumberLabel(order)}</h1>
          <p className="text-sm text-muted-foreground">Placed {getRelativeTime(order.created_at, 'long')}</p>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Progress</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {steps.map((s, i) => (
            <div key={s.key} className="flex gap-3">
              <div className="flex flex-col items-center pt-0.5">
                {s.done ? (
                  <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                ) : s.action ? (
                  <Clock className="w-5 h-5 text-amber-500 shrink-0" />
                ) : (
                  <Circle className="w-5 h-5 text-muted-foreground/40 shrink-0" />
                )}
                {i < steps.length - 1 && <div className="w-px flex-1 min-h-[16px] bg-border my-1" />}
              </div>
              <div className="flex-1 pb-2">
                <p className={`font-medium ${s.action && !s.done ? 'text-amber-700 dark:text-amber-400' : ''}`}>
                  {s.label}
                  {s.action && !s.done && (
                    <Badge variant="secondary" className="ml-2 text-[10px]">
                      Action required
                    </Badge>
                  )}
                </p>
                {s.at && <p className="text-xs text-muted-foreground">{getRelativeTime(s.at)}</p>}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {order.status === 'pending' && (
        <Card className="border-blue-200 bg-blue-50/50 dark:bg-blue-950/20">
          <CardContent className="pt-6 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">Payment before shipping</p>
            <p className="mt-1">
              This order is not paid yet. Do not ship until payment clears in escrow. SmartDalali does not offer
              pay-on-delivery for marketplace orders.
            </p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Delivery</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start justify-between gap-2">
            <div className="flex gap-2 min-w-0">
              <MapPin className="w-4 h-4 text-muted-foreground shrink-0 mt-1" />
              <p className="text-sm whitespace-pre-wrap">{order.shipping_address}</p>
            </div>
            <Button type="button" variant="outline" size="sm" className="shrink-0 gap-1" onClick={copyAddr}>
              <Copy className="w-3.5 h-3.5" />
              Copy
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            {(() => {
              const callTarget = String(order.shipping_phone || '').trim();
              const whatsappTarget = waLink(order.shipping_phone);
              const hasPhone = callTarget.length > 0 && whatsappTarget !== '#';
              return (
                <>
            <Button variant="outline" size="sm" className="gap-2" asChild>
              <a href={hasPhone ? `tel:${callTarget}` : '#'} aria-disabled={!hasPhone}>
                <Phone className="w-4 h-4" />
                Call
              </a>
            </Button>
            <Button variant="outline" size="sm" className="gap-2" asChild>
              <a
                href={whatsappTarget}
                target={hasPhone ? '_blank' : undefined}
                rel={hasPhone ? 'noreferrer' : undefined}
                aria-disabled={!hasPhone}
              >
                <MessageCircle className="w-4 h-4" />
                WhatsApp
              </a>
            </Button>
                </>
              );
            })()}
            <Button variant="secondary" size="sm" className="gap-2" onClick={() => void openChat()}>
              <MessageCircle className="w-4 h-4" />
              Chat in app
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Products</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {order.items.map((item) => {
            const img = commerceOrderItemImage(item);
            return (
              <div key={item.id} className="flex gap-3 items-center">
                <div className="w-14 h-14 rounded-lg bg-muted overflow-hidden shrink-0 relative">
                  {img ? (
                    <img src={img} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <Package className="w-6 h-6 m-4 text-muted-foreground" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{commerceOrderItemTitle(item)}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatTZS(commerceOrderItemUnitPrice(item))} × {item.quantity}
                  </p>
                </div>
                <p className="font-semibold shrink-0">{formatTZS(commerceOrderItemLineTotal(item))}</p>
              </div>
            );
          })}
          <Separator />
          <div className="flex justify-between font-semibold">
            <span>Total</span>
            <span>{formatTZS(orderTotalAmount(order))}</span>
          </div>
        </CardContent>
      </Card>

      {disputeFocus && order.status === 'disputed' && (
        <Card className="border-orange-300 bg-orange-50/40 dark:bg-orange-950/20">
          <CardHeader>
            <CardTitle className="text-lg text-orange-800 dark:text-orange-300">Dispute</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Respond from the orders list dispute dialog, or contact support if you need help.
            </p>
            <Button className="mt-3" variant="outline" onClick={() => router.push(`${routes.sellerOrders()}?status=disputed`)}>
              Open dispute tools
            </Button>
          </CardContent>
        </Card>
      )}

      {canShip && (
        <div className="fixed bottom-0 left-0 right-0 p-4 bg-background/95 border-t backdrop-blur md:static md:border-0 md:bg-transparent md:p-0">
          <Button className="w-full h-12 text-base gap-2" onClick={() => setShipOpen(true)}>
            <Truck className="w-5 h-5" />
            Mark as shipped
          </Button>
        </div>
      )}

      {shipDone && (
        <Card className="border-emerald-200 bg-emerald-50/50 dark:bg-emerald-950/20">
          <CardContent className="pt-6 text-sm text-muted-foreground">
            Done! The buyer has been notified. Funds will be released automatically in {AUTO_CONFIRM_DAYS} days if they
            don&apos;t confirm first.
          </CardContent>
        </Card>
      )}

      <Drawer open={shipOpen} onOpenChange={setShipOpen}>
        <DrawerContent className="max-h-[92vh]">
          <DrawerHeader>
            <DrawerTitle>Ship this order</DrawerTitle>
            <DrawerDescription>
              Upload a photo or video of the sealed parcel. This protects you if the buyer opens a dispute.
            </DrawerDescription>
          </DrawerHeader>
          <div className="px-4 space-y-4 overflow-y-auto">
            <div className="space-y-2">
              <Label>Photo or video (required)</Label>
              <Input
                type="file"
                accept="image/*,video/*"
                multiple={false}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  if (f.type.startsWith('video/')) {
                    setShipmentVideo(f);
                    setShipmentImages([]);
                  } else {
                    setShipmentImages([f]);
                    setShipmentVideo(null);
                  }
                }}
              />
              {hasEvidence && (
                <p className="text-xs text-emerald-600">
                  {shipmentVideo ? `Video: ${shipmentVideo.name}` : `Photo: ${shipmentImages[0]?.name}`}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label>Tracking number (optional)</Label>
              <Input value={trackingNumber} onChange={(e) => setTrackingNumber(e.target.value)} placeholder="e.g. TRK123" />
            </div>
            <div className="space-y-2">
              <Label>Carrier (optional)</Label>
              <Input value={carrier} onChange={(e) => setCarrier(e.target.value)} placeholder="DHL, bus office…" />
            </div>
          </div>
          <DrawerFooter className="flex-col gap-2">
            <Button className="w-full gap-2" disabled={shipping || !hasEvidence} onClick={() => void submitShip()}>
              {shipping ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Confirm shipment
            </Button>
            <DrawerClose asChild>
              <Button variant="outline" className="w-full">
                Cancel
              </Button>
            </DrawerClose>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>
    </div>
  );
}
