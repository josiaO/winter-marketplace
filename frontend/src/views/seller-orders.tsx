'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { routes } from '@/lib/routes';
import { useState, useEffect, useMemo, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Package, Clock, MapPin, Loader2, PackageOpen, ShieldAlert, Send, ImageOff, ChevronLeft } from 'lucide-react';
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
    return { ring: 'ring-red-100 dark:ring-red-900/30', badge: 'bg-red-100 text-red-800 dark:bg-red-400/20 dark:text-red-400', label: 'Disputed' };
  }
  if (order.status === 'pending') {
    return { ring: 'ring-blue-100 dark:ring-blue-900/30', badge: 'bg-blue-50 text-blue-700 dark:bg-blue-400/20 dark:text-blue-400', label: 'Awaiting payment' };
  }
  if (order.status === 'confirmed' || order.status === 'processing') {
    return { ring: 'ring-orange-100 dark:ring-orange-900/30', badge: 'bg-orange-100 text-orange-900 dark:bg-orange-400/20 dark:text-orange-400', label: 'Action: Ship now' };
  }
  if (order.status === 'shipped' || order.status === 'arrived') {
    return { ring: 'ring-sky-100 dark:ring-sky-900/30', badge: 'bg-sky-50 text-sky-700 dark:bg-sky-400/20 dark:text-sky-400', label: 'In transit' };
  }
  if (order.status === 'delivered' || order.status === 'completed') {
    return { ring: 'ring-emerald-100 dark:ring-emerald-900/30', badge: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-400/20 dark:text-emerald-400', label: 'Completed' };
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
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
      >
        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            size="icon"
            className="rounded-full shadow-sm bg-white shrink-0"
            onClick={() => router.push(routes.sellerDashboard())}
          >
            <ChevronLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">Orders</h1>
            <p className="text-muted-foreground mt-1">
              Your daily work table — tap an order to manage it.
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          className="gap-2 shrink-0"
          onClick={() => router.push(routes.sellerDashboard())}
        >
          <Package className="w-4 h-4" />
          Dashboard
        </Button>
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
                <Card className={`overflow-hidden border-0 shadow-lg shadow-black/[0.02] ring-1 ${tone.ring} bg-white/40 dark:bg-zinc-900/40 backdrop-blur-sm transition-all hover:shadow-xl hover:ring-primary/20`}>
                  <CardContent className="p-0">
                    <Link href={routes.sellerOrder(String(order.id))} className="block p-5 sm:p-6 group">
                      <div className="flex flex-col sm:flex-row gap-5">
                        <div className="w-full sm:w-28 h-28 rounded-2xl bg-muted overflow-hidden shrink-0 relative shadow-inner ring-1 ring-black/5">
                          {img ? (
                            <img src={img} alt="" className="w-full h-full object-contain group-hover:scale-105 transition-transform duration-500" />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center">
                              <ImageOff className="w-8 h-8 text-muted-foreground/30" />
                            </div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0 flex flex-col justify-between py-1">
                          <div className="space-y-1.5">
                            <div className="flex items-center justify-between gap-2">
                               <div className="flex items-center gap-2">
                                 <span className="font-bold text-foreground text-sm tracking-tight opacity-70">#{orderNumberLabel(order)}</span>
                                 <Badge className={`${tone.badge} border-0 font-bold px-2 py-0.5 rounded-md text-[11px]`}>{tone.label}</Badge>
                               </div>
                               <span className="text-xs font-bold text-muted-foreground/60">{getRelativeTime(order.created_at)}</span>
                            </div>
                            <h3 className="text-lg font-bold text-foreground leading-tight line-clamp-1">{title}</h3>
                            <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs font-bold text-muted-foreground/80">
                              <span className="flex items-center gap-1.5">
                                <Package className="w-3.5 h-3.5 opacity-40" />
                                {buyerLabel(order)}
                              </span>
                              <span className="flex items-center gap-1.5 truncate max-w-[150px]">
                                <MapPin className="w-3.5 h-3.5 opacity-40" />
                                {order.shipping_address?.split(',').slice(-1).join(',').trim() || 'TZ'}
                              </span>
                            </div>
                          </div>
                          <div className="flex items-center justify-between mt-auto pt-4 border-t border-black/5 dark:border-white/5">
                             <p className="text-xl font-black text-foreground">{formatTZS(orderTotalAmount(order))}</p>
                             <div className="flex gap-2">
                               {order.status === 'disputed' && (
                                 <Button
                                   size="sm"
                                   variant="outline"
                                   className="border-red-500/50 text-red-600 font-bold h-9 rounded-xl"
                                   onClick={(e) => {
                                     e.preventDefault();
                                     setRespondDisputeDialogOrder(order);
                                   }}
                                 >
                                   <ShieldAlert className="w-4 h-4 mr-1.5" />
                                   Evidence
                                 </Button>
                               )}
                               <Button size="sm" className="font-bold h-9 rounded-xl shadow-md shadow-primary/20">
                                 {cta.label}
                               </Button>
                             </div>
                          </div>
                        </div>
                      </div>
                    </Link>
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
