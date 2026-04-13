'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import {
  Package,
  ChevronRight,
  ClipboardList,
  RotateCcw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { EmptyState } from '@/components/smartdalali/empty-state';
import { OrderStatusBadge } from '@/components/smartdalali/order-status-badge';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, formatDate, orderNumberLabel, orderTotalAmount } from '@/lib/helpers';
import { toast } from 'sonner';
import type { Order as DjangoOrder } from '@/types/api';

const ORDER_TABS = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'shipped', label: 'Shipped' },
  { value: 'delivered', label: 'Delivered' },
  { value: 'cancelled', label: 'Cancelled' },
];

export function OrdersPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  const [orders, setOrders] = useState<DjangoOrder[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');
  const [buyAgainOrderId, setBuyAgainOrderId] = useState<number | null>(null);

  const fetchOrders = useCallback(async () => {
    if (!isAuthenticated) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const res = await api.commerce.orders({ role: 'buyer' });
      // The endpoint returns PaginatedResponse<Order> → extract results
      const data = Array.isArray(res) ? res : (res.results ?? []);
      setOrders(Array.isArray(data) ? data : []);
    } catch {
      toast.error('Failed to load orders');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const handleBuyAgain = useCallback(
    async (e: React.MouseEvent, order: DjangoOrder) => {
      e.stopPropagation();
      if (!order.items.length) {
        toast.error('This order has no items to reorder.');
        return;
      }
      setBuyAgainOrderId(order.id);
      try {
        let added = 0;
        let lastMessage = '';

        for (const item of order.items) {
          const listing: any = item.listing;
          const listingId = listing?.id;
          if (!listingId) {
            const browse = window.confirm(
              'This product is no longer available. Browse similar items?',
            );
            if (browse) {
              router.push(routes.home());
            }
            continue;
          }

          const latest = await api.listings.detail(String(listingId));
          const currentStock =
            typeof latest.stock_quantity === 'number' ? latest.stock_quantity : undefined;

          if (currentStock !== undefined && currentStock < 1) {
            const notify = window.confirm(
              'This item is currently out of stock. Notify me when available?',
            );
            if (notify) {
              toast.success('We will remember this item in your wishlist for later.');
            }
            continue;
          }

          const qty = Number(item.quantity || 1);
          await api.commerce.cartAddItem({ listing_id: listingId, quantity: qty });
          added += 1;

          const previousPrice = Number(item.price_at_time ?? latest.price ?? 0);
          const currentPrice = Number(latest.price ?? 0);
          if (currentPrice !== previousPrice) {
            lastMessage = `Added to cart at current price: ${formatTZS(currentPrice)} (Price was ${formatTZS(previousPrice)} when you last bought)`;
          } else {
            lastMessage = `Added to cart at current price: ${formatTZS(currentPrice)}`;
          }
        }

        if (added > 0) {
          toast.success(lastMessage || 'Added to cart');
        }
      } catch {
        toast.error('Could not buy this item again right now.');
      } finally {
        setBuyAgainOrderId(null);
      }
    },
    [router],
  );

  const filteredOrders =
    activeTab === 'all'
      ? orders
      : orders.filter((o) => o.status === activeTab);

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-8 w-40 mb-6" />
        <div className="flex gap-2 mb-6">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-9 w-20 rounded-lg" />
          ))}
        </div>
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-36 rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <EmptyState
          icon={ClipboardList}
          title="Please login to view orders"
          description="You need to be logged in to view your order history."
          actionLabel="Login"
          onAction={() => router.push(routes.login())}
        />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-6">
          My Orders
        </h1>

        {/* Filter Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-6">
          <TabsList className="flex flex-wrap gap-1 h-auto bg-transparent p-0">
            {ORDER_TABS.map((tab) => (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className="rounded-full px-4 py-2 text-sm font-medium data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=inactive]:bg-muted data-[state=inactive]:text-muted-foreground"
              >
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {/* Orders List */}
        {filteredOrders.length === 0 ? (
          <EmptyState
            icon={Package}
            title={
              activeTab === 'all'
                ? 'No orders yet'
                : `No ${activeTab} orders`
            }
            description={
              activeTab === 'all'
                ? 'When you place an order, it will appear here.'
                : `You don't have any ${activeTab} orders.`
            }
            actionLabel="Continue Shopping"
            onAction={() => router.push(routes.home())}
          />
        ) : (
          <div className="space-y-4">
            {filteredOrders.map((order, index) => (
              <motion.div
                key={order.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                className="border rounded-xl bg-card overflow-hidden hover:shadow-md transition-shadow cursor-pointer"
                onClick={() =>
                  router.push(routes.order(String(order.id)))
                }
              >
                <div className="p-4 sm:p-5">
                  {/* Header */}
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-mono font-medium text-foreground">
                          #{orderNumberLabel(order as any)}
                        </span>
                        <OrderStatusBadge status={order.status} />
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {formatDate(order.created_at)}
                      </p>
                    </div>
                    <span className="text-sm font-semibold text-foreground">
                      {formatTZS(orderTotalAmount(order as any))}
                    </span>
                  </div>

                  {/* Items Preview */}
                  <div className="flex items-center gap-3 overflow-hidden">
                    <div className="flex -space-x-2">
                      {order.items.slice(0, 4).map((item) => (
                        // Backend returns `OrderItemSerializer` with `listing` embedded.
                        <div
                          key={item.id}
                          className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg overflow-hidden border-2 border-background bg-muted flex-shrink-0"
                        >
                          {(() => {
                            const l: any = (item as any).listing;
                            const url =
                              l?.images?.[0]?.image ||
                              l?.media?.[0]?.file_url ||
                              l?.media?.[0]?.file ||
                              null;
                            return url ? (
                            <Image
                              src={url}
                              alt={String(l?.title || 'Item')}
                              width={48}
                              height={48}
                              className="w-full h-full object-cover"
                            />
                            ) : (
                            <div className="w-full h-full flex items-center justify-center">
                              <Package className="w-4 h-4 text-muted-foreground/30" />
                            </div>
                            );
                          })()}
                        </div>
                      ))}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-foreground truncate">
                        {(() => {
                          const first: any = order.items[0];
                          const title = first?.listing?.title || first?.listing_title || 'Item';
                          return order.items.length === 1
                            ? title
                            : `${title} +${order.items.length - 1} more`;
                        })()}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {order.items.length}{' '}
                        {order.items.length === 1 ? 'item' : 'items'}
                      </p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  </div>
                  {order.status === 'completed' && (
                    <div className="mt-4 flex justify-end">
                      <Button
                        size="sm"
                        variant="outline"
                        className="rounded-lg"
                        onClick={(e) => void handleBuyAgain(e, order)}
                        disabled={buyAgainOrderId === order.id}
                      >
                        {buyAgainOrderId === order.id ? (
                          <span className="inline-flex items-center gap-2">
                            <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                            Adding...
                          </span>
                        ) : (
                          <>
                            <RotateCcw className="w-4 h-4 mr-2" />
                            Buy Again
                          </>
                        )}
                      </Button>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  );
}
