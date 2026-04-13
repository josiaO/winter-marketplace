'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { routes } from '@/lib/routes';
import { useState, useEffect, useMemo, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Package, Clock, MapPin, Loader2, PackageOpen, ShieldAlert, Send, ImageOff } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent } from '@/components/ui/card';
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
  getRelativeTime,
  getStatusLabel,
  orderNumberLabel,
  orderTotalAmount,
  commerceOrderItemTitle,
  commerceOrderItemImage,
} from '@/lib/helpers';
import { ApiClientError } from '@/types/api';
import { EmptyState } from '@/components/smartdalali/empty-state';
import type { Order, PaginatedResponse } from '@/types/api';

const TABS = [
  { value: 'all', label: 'All' },
  { value: 'new', label: 'Awaiting buyer payment' },
  { value: 'to_ship', label: 'To ship' },
  { value: 'shipped', label: 'Shipped' },
  { value: 'completed', label: 'Completed' },
  { value: 'disputed', label: 'Disputed' },
] as const;

function tabFilter(tab: string, o: Order): boolean {
  if (tab === 'all') return true;
  if (tab === 'new') return o.status === 'pending';
  if (tab === 'to_ship') return o.status === 'confirmed' || o.status === 'processing';
  if (tab === 'shipped') return o.status === 'shipped' || o.status === 'arrived';
  if (tab === 'completed') return o.status === 'delivered' || o.status === 'completed';
  if (tab === 'disputed') return o.status === 'disputed';
  return true;
}

function statusTone(order: Order): { ring: string; badge: string; label: string } {
  if (order.status === 'disputed') {
    return { ring: 'ring-red-200', badge: 'bg-red-100 text-red-800', label: 'Disputed' };
  }
  if (order.status === 'pending') {
    return { ring: 'ring-blue-200', badge: 'bg-blue-100 text-blue-800', label: 'Awaiting payment' };
  }
  if (order.status === 'confirmed' || order.status === 'processing') {
    return { ring: 'ring-amber-200', badge: 'bg-amber-100 text-amber-900', label: 'Needs shipment' };
  }
  if (order.status === 'shipped' || order.status === 'arrived') {
    return { ring: 'ring-sky-200', badge: 'bg-sky-100 text-sky-900', label: 'In transit' };
  }
  if (order.status === 'delivered' || order.status === 'completed') {
    return { ring: 'ring-emerald-200', badge: 'bg-emerald-100 text-emerald-900', label: 'Completed' };
  }
  return { ring: 'ring-border', badge: 'bg-muted text-foreground', label: getStatusLabel(order.status) };
}

function buyerLabel(order: Order): string {
  const b = order.buyer;
  if (!b) return 'Buyer';
  const n = [b.first_name, b.last_name].filter(Boolean).join(' ');
  return n || b.username;
}

export function SellerOrdersPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>('all');

  const [respondDisputeDialogOrder, setRespondDisputeDialogOrder] = useState<Order | null>(null);
  const [disputeResponseNotes, setDisputeResponseNotes] = useState('');
  const [disputeResponseImages, setDisputeResponseImages] = useState<File[]>([]);
  const [disputeResponseVideo, setDisputeResponseVideo] = useState<File | null>(null);
  const [isRespondingDispute, setIsRespondingDispute] = useState(false);

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

  const searchParams = useSearchParams();
  const statusParam = searchParams.get('status');

  useEffect(() => {
    if (statusParam === 'disputed') setActiveTab('disputed');
  }, [statusParam]);

  useEffect(() => {
    if (isAuthenticated && user && canAccessSellerPortal(user)) {
      void loadOrders();
    }
  }, [isAuthenticated, user, loadOrders]);

  const filtered = useMemo(
    () => orders.filter((o) => tabFilter(activeTab, o)),
    [orders, activeTab],
  );

  const primaryCta = (order: Order) => {
    if (order.status === 'disputed') return { label: 'Respond to dispute', href: routes.sellerOrder(String(order.id)) };
    if (order.status === 'pending') return { label: 'View order', href: routes.sellerOrder(String(order.id)) };
    if (order.status === 'confirmed' || order.status === 'processing')
      return { label: 'Mark shipped', href: routes.sellerOrder(String(order.id)) };
    return { label: 'View', href: routes.sellerOrder(String(order.id)) };
  };

  const handleRespondDispute = async () => {
    if (!respondDisputeDialogOrder || !respondDisputeDialogOrder.dispute) return;
    setIsRespondingDispute(true);
    try {
      await api.escrow.respondDispute(respondDisputeDialogOrder.dispute.id, {
        notes: disputeResponseNotes.trim(),
        evidence_video: disputeResponseVideo || undefined,
        evidence_images: disputeResponseImages.length > 0 ? disputeResponseImages : undefined,
      });
      toast.success('Response submitted to dispute resolution team.');
      setRespondDisputeDialogOrder(null);
      setDisputeResponseNotes('');
      setDisputeResponseImages([]);
      setDisputeResponseVideo(null);
      await loadOrders();
    } catch {
      toast.error('Failed to submit response.');
    } finally {
      setIsRespondingDispute(false);
    }
  };

  if (!isAuthenticated || !user) return null;

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl sm:text-3xl font-bold text-foreground">Orders</h1>
        <p className="text-muted-foreground mt-1">Your daily work table — tap an order to manage it.</p>
      </motion.div>

      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
        {TABS.map((tab) => (
          <Button
            key={tab.value}
            type="button"
            variant={activeTab === tab.value ? 'default' : 'outline'}
            size="sm"
            className="shrink-0 rounded-full"
            onClick={() => setActiveTab(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-36 w-full rounded-2xl" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={PackageOpen}
          title="No orders in this view"
          description="When buyers pay, orders land here with clear next steps."
        />
      ) : (
        <div className="space-y-4">
          {filtered.map((order) => {
            const item = order.items?.[0];
            const img = item ? commerceOrderItemImage(item) : null;
            const title = item ? commerceOrderItemTitle(item) : 'Order';
            const tone = statusTone(order);
            const cta = primaryCta(order);
            return (
              <motion.div key={order.id} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                <Card className={`overflow-hidden border-0 shadow-md ring-2 ${tone.ring} shadow-black/5`}>
                  <CardContent className="p-0">
                    <Link href={routes.sellerOrder(String(order.id))} className="block p-4 sm:p-5 hover:bg-muted/30">
                      <div className="flex flex-col sm:flex-row gap-4">
                        <div className="w-full sm:w-24 h-24 rounded-xl bg-muted overflow-hidden shrink-0 relative">
                          {img ? (
                            <img src={img} alt="" className="w-full h-full object-cover" />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center">
                              <ImageOff className="w-8 h-8 text-muted-foreground/40" />
                            </div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0 space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-foreground">#{orderNumberLabel(order)}</span>
                            <Badge className={tone.badge}>{tone.label}</Badge>
                          </div>
                          <p className="text-sm text-foreground font-medium truncate">{title}</p>
                          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <Package className="w-3.5 h-3.5" />
                              {buyerLabel(order)}
                            </span>
                            <span className="flex items-center gap-1">
                              <MapPin className="w-3.5 h-3.5" />
                              {order.shipping_address?.split(',').slice(-2).join(',').trim() || '—'}
                            </span>
                            <span className="flex items-center gap-1">
                              <Clock className="w-3.5 h-3.5" />
                              {getRelativeTime(order.created_at, 'long')}
                            </span>
                          </div>
                          <p className="text-lg font-bold text-foreground">{formatTZS(orderTotalAmount(order))}</p>
                        </div>
                      </div>
                    </Link>
                    <div className="flex flex-wrap gap-2 px-4 sm:px-5 pb-4">
                      <Button asChild className="flex-1 sm:flex-none">
                        <Link href={cta.href}>{cta.label}</Link>
                      </Button>
                      {order.status === 'disputed' && (
                        <Button
                          variant="outline"
                          className="flex-1 sm:flex-none border-orange-400 text-orange-700"
                          onClick={(e) => {
                            e.preventDefault();
                            setRespondDisputeDialogOrder(order);
                          }}
                        >
                          <ShieldAlert className="w-4 h-4 mr-1" />
                          Upload evidence
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}

      <Dialog
        open={!!respondDisputeDialogOrder}
        onOpenChange={(open) => {
          if (!open) {
            setRespondDisputeDialogOrder(null);
            setDisputeResponseNotes('');
            setDisputeResponseImages([]);
            setDisputeResponseVideo(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-orange-600">
              <ShieldAlert className="w-5 h-5" />
              Respond to dispute
            </DialogTitle>
            <DialogDescription>
              Provide evidence for order #{respondDisputeDialogOrder?.order_number?.slice(-8)}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="response-notes">Explanation</Label>
              <textarea
                id="response-notes"
                className="w-full min-h-[100px] p-3 rounded-xl border bg-background text-sm focus:ring-2 focus:ring-primary/20 outline-none resize-none"
                placeholder="Explain your side…"
                value={disputeResponseNotes}
                onChange={(e) => setDisputeResponseNotes(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label>Photos</Label>
              <Input
                type="file"
                multiple
                accept="image/*"
                onChange={(e) => {
                  const files = Array.from(e.target.files || []);
                  setDisputeResponseImages(files);
                }}
                className="cursor-pointer"
              />
            </div>

            <div className="space-y-2">
              <Label>Video (optional)</Label>
              <Input
                type="file"
                accept="video/*"
                onChange={(e) => {
                  const file = e.target.files?.[0] || null;
                  setDisputeResponseVideo(file);
                }}
                className="cursor-pointer"
              />
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setRespondDisputeDialogOrder(null)} disabled={isRespondingDispute}>
              Cancel
            </Button>
            <Button
              onClick={handleRespondDispute}
              disabled={isRespondingDispute || !disputeResponseNotes.trim()}
              className="bg-orange-600 hover:bg-orange-700 text-white gap-2"
            >
              {isRespondingDispute ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Submitting…
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  Submit
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
