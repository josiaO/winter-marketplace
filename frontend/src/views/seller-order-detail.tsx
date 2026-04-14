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
  MoreHorizontal,
  ExternalLink,
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

      <Card className="border-0 shadow-lg shadow-black/[0.02] bg-white/40 dark:bg-zinc-900/40 backdrop-blur-sm ring-1 ring-black/5 dark:ring-white/5 overflow-hidden">
        <CardHeader className="pb-4 border-b border-black/5 dark:border-white/5">
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <Clock className="w-4 h-4 text-primary" />
            Order Journey
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-6 relative">
          {/* Vertical line connector */}
          <div className="absolute left-[27px] top-[40px] bottom-[40px] w-0.5 bg-muted/60" />
          
          <div className="space-y-8 relative">
            {steps.map((s, i) => (
              <div key={s.key} className="flex gap-4">
                <div className="relative z-10 flex items-center justify-center w-7 h-7 rounded-full bg-background ring-4 ring-background">
                  {s.done ? (
                    <div className="w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center">
                      <CheckCircle2 className="w-3.5 h-3.5 text-white" />
                    </div>
                  ) : s.action ? (
                    <div className="w-5 h-5 rounded-full bg-orange-500 flex items-center justify-center animate-pulse">
                      <Clock className="w-3.5 h-3.5 text-white" />
                    </div>
                  ) : (
                    <div className="w-5 h-5 rounded-full bg-muted border-2 border-muted-foreground/20" />
                  )}
                </div>
                <div className="flex-1 -mt-0.5">
                  <div className="flex items-center gap-2">
                    <p className={`text-sm font-bold ${s.done ? 'text-foreground' : 'text-muted-foreground'}`}>
                      {s.label}
                    </p>
                    {s.action && !s.done && (
                      <Badge className="bg-orange-100 text-orange-900 dark:bg-orange-500/20 dark:text-orange-400 border-0 text-[10px] font-bold">
                        ACTION NEEDED
                      </Badge>
                    )}
                  </div>
                  {s.at ? (
                    <p className="text-[11px] font-bold text-muted-foreground/60 uppercase tracking-wider mt-0.5">
                      {getRelativeTime(s.at)}
                    </p>
                  ) : !s.done && (
                    <p className="text-[11px] font-medium text-muted-foreground/40 mt-0.5 italic">
                      Pending...
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
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

      <Card className="border-0 shadow-lg shadow-black/[0.02] bg-white/40 dark:bg-zinc-900/40 backdrop-blur-sm ring-1 ring-black/5 dark:ring-white/5">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
          <CardTitle className="text-base font-bold flex items-center gap-2">
            <MapPin className="w-4 h-4 text-primary" />
            Shipment Details
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="p-4 rounded-2xl bg-white/50 dark:bg-black/20 ring-1 ring-black/5 dark:ring-white/5 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1">
                 <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-widest opacity-60">Buyer Address</p>
                 <p className="text-sm font-bold leading-relaxed">{order.shipping_address}</p>
              </div>
              <Button type="button" variant="ghost" size="icon" className="shrink-0 h-8 w-8 rounded-lg" onClick={copyAddr}>
                <Copy className="w-4 h-4" />
              </Button>
            </div>
            
            <div className="flex flex-wrap gap-2.5">
              {(() => {
                const callTarget = String(order.shipping_phone || '').trim();
                const whatsappTarget = waLink(order.shipping_phone);
                const hasPhone = callTarget.length > 0 && whatsappTarget !== '#';
                return (
                  <>
                    <Button variant="outline" size="sm" className="rounded-xl h-10 px-4 font-bold border-emerald-500/20 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-50 bg-emerald-50/50" asChild>
                      <a href={hasPhone ? `tel:${callTarget}` : '#'} aria-disabled={!hasPhone}>
                        <Phone className="w-3.5 h-3.5 mr-2" />
                        Call Buyer
                      </a>
                    </Button>
                    <Button variant="outline" size="sm" className="rounded-xl h-10 px-4 font-bold border-green-500/20 text-green-700 dark:text-green-400 hover:bg-green-50 bg-green-50/50" asChild>
                      <a
                        href={whatsappTarget}
                        target={hasPhone ? '_blank' : undefined}
                        rel={hasPhone ? 'noreferrer' : undefined}
                        aria-disabled={!hasPhone}
                      >
                        <MessageCircle className="w-3.5 h-3.5 mr-2" />
                        WhatsApp
                      </a>
                    </Button>
                  </>
                );
              })()}
              <Button variant="secondary" size="sm" className="rounded-xl h-10 px-4 font-bold gap-2" onClick={() => void openChat()}>
                <MessageCircle className="w-3.5 h-3.5" />
                In-app Chat
              </Button>
            </div>
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
