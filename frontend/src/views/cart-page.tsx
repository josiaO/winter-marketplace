'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback, useRef } from 'react';
import Image from 'next/image';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Minus,
  Plus,
  Trash2,
  ShoppingBag,
  ArrowRight,
  ArrowLeft,
  Package,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { EmptyState } from '@/components/smartdalali/empty-state';
import { PriceDisplay } from '@/components/smartdalali/price-display';
import { useAuthStore, useCartStore } from '@/store';
import { api } from '@/lib/api-client';
import { adaptDjangoCart } from '@/lib/django-cart-adapter';
import { formatTZS } from '@/lib/helpers';
import { toast } from 'sonner';
import { ApiClientError } from '@/types/api';

// ---------------------------------------------------------------------------

export function CartPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const { cart, setCart } = useCartStore();
  const [serverCartTotal, setServerCartTotal] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isRemoving, setIsRemoving] = useState<string | null>(null);
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);
  const [itemToRemove, setItemToRemove] = useState<string | null>(null);
  const [quantityBusyByLine, setQuantityBusyByLine] = useState<
    Record<string, boolean>
  >({});
  const queueRef = useRef<Promise<void>>(Promise.resolve());
  const debounceRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  /** Fetch Django cart, adapt, and push into the store. */
  const fetchAndSetCart = useCallback(async () => {
    try {
      const djangoCart = await api.commerce.cart();
      setServerCartTotal(Number(djangoCart.total));
      setCart(adaptDjangoCart(djangoCart));
    } catch (err: unknown) {
      const msg =
        err instanceof ApiClientError
          ? err.detail || err.message
          : 'Failed to load cart';
      toast.error(msg);
    }
  }, [setCart]);

  useEffect(() => {
    if (!isAuthenticated) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    fetchAndSetCart().finally(() => setIsLoading(false));
  }, [isAuthenticated, fetchAndSetCart]);

  useEffect(() => {
    return () => {
      // Cleanup all debounces
      Object.values(debounceRef.current).forEach(clearTimeout);
    };
  }, []);

  const setLineQuantityBusy = useCallback((lineId: string, busy: boolean) => {
    setQuantityBusyByLine((prev) => {
      const next = { ...prev };
      if (busy) next[lineId] = true;
      else delete next[lineId];
      return next;
    });
  }, []);

  /**
   * Processes a cart action sequentially to prevent race conditions
   * where multiple in-flight requests clobber each other's state updates.
   */
  const enqueueCartAction = useCallback((action: () => Promise<void>) => {
    queueRef.current = queueRef.current.then(action).catch((err) => {
      console.error('Cart action failed:', err);
    });
    return queueRef.current;
  }, []);

  const handleUpdateQuantity = useCallback(
    (cartItemId: string, listingId: string, newQuantity: number) => {
      if (!isAuthenticated) return;

      // Optimistically update the store if possible, 
      // but for now we'll rely on the queue to keep it safe.
      
      if (debounceRef.current[cartItemId]) {
        clearTimeout(debounceRef.current[cartItemId]);
      }

      debounceRef.current[cartItemId] = setTimeout(() => {
        enqueueCartAction(async () => {
          setLineQuantityBusy(cartItemId, true);
          try {
            const djangoCart = await api.commerce.cartSetItemQuantity(
              cartItemId,
              listingId,
              newQuantity,
            );
            setServerCartTotal(Number(djangoCart.total));
            setCart(adaptDjangoCart(djangoCart));
          } catch (err: unknown) {
            const msg =
              err instanceof ApiClientError
                ? err.detail ||
                  err.message ||
                  'Could not update quantity (check stock).'
                : 'Failed to update quantity';
            toast.error(msg);
            await fetchAndSetCart();
          } finally {
            setLineQuantityBusy(cartItemId, false);
          }
        });
      }, 300);
    },
    [isAuthenticated, setCart, setLineQuantityBusy, fetchAndSetCart, enqueueCartAction],
  );

  const handleConfirmRemove = useCallback(async () => {
    if (!isAuthenticated || !itemToRemove) return;
    
    enqueueCartAction(async () => {
      setIsRemoving(itemToRemove);
      try {
        await api.commerce.cartRemoveItem({ item_id: itemToRemove });
        await fetchAndSetCart();
        toast.success('Item removed from cart');
      } catch (err: unknown) {
        const msg =
          err instanceof ApiClientError
            ? err.detail || err.message
            : 'Failed to remove item';
        toast.error(msg);
      } finally {
        setIsRemoving(null);
        setRemoveDialogOpen(false);
        setItemToRemove(null);
      }
    });
  }, [isAuthenticated, itemToRemove, fetchAndSetCart, enqueueCartAction]);

  const items = cart?.items || [];

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-8 w-32 mb-6" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex gap-4 p-4 rounded-xl border">
                <Skeleton className="w-24 h-24 rounded-lg flex-shrink-0" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-5 w-1/3" />
                  <Skeleton className="h-8 w-32" />
                </div>
              </div>
            ))}
          </div>
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <EmptyState
          icon={ShoppingBag}
          title="Please login to view your cart"
          description="You need to be logged in to manage your shopping cart."
          actionLabel="Login"
          onAction={() => router.push(routes.login())}
        />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <EmptyState
          icon={ShoppingBag}
          title="Your cart is empty"
          description="Looks like you haven't added any items to your cart yet."
          actionLabel="Continue Shopping"
          onAction={() => router.push(routes.home())}
        />
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-6">
          Shopping Cart
        </h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Cart Items */}
          <div className="lg:col-span-2 space-y-3">
            <AnimatePresence>
              {items.map((item) => {
                const qtyBusy = Boolean(quantityBusyByLine[item.id]);
                return (
                <motion.div
                  key={item.id}
                  layout
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20, height: 0 }}
                  className="flex gap-4 p-4 rounded-xl border bg-card"
                >
                  {/* Image */}
                  <div
                    className="relative w-20 h-20 sm:w-24 sm:h-24 rounded-lg overflow-hidden bg-muted flex-shrink-0 cursor-pointer"
                    onClick={() =>
                      router.push(routes.product(String(item.listing.id)))
                    }
                  >
                    {item.listing.images?.[0]?.url || item.listing.image ? (
                      <Image
                        src={
                          item.listing.images?.[0]?.url ||
                          item.listing.image ||
                          ''
                        }
                        alt={item.listing.title}
                        fill
                        className="object-cover"
                        sizes="96px"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Package className="w-8 h-8 text-muted-foreground/30" />
                      </div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <h3
                      className="text-sm sm:text-base font-medium text-foreground line-clamp-2 cursor-pointer hover:text-primary transition-colors"
                      onClick={() =>
                        router.push(routes.product(String(item.listing.id)))
                      }
                    >
                      {item.listing.title}
                    </h3>
                    <PriceDisplay
                      price={item.listing.price}
                      size="sm"
                      className="mt-1"
                    />

                    {/* Quantity Controls */}
                    <div className="flex items-center justify-between mt-3">
                      <div className="flex items-center border rounded-lg">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 rounded-r-none"
                          onClick={() =>
                            handleUpdateQuantity(
                              item.id,
                              item.listingId,
                              Math.max(1, item.quantity - 1),
                            )
                          }
                          disabled={item.quantity <= 1 || qtyBusy}
                        >
                          <Minus className="w-3.5 h-3.5" />
                        </Button>
                        <span className="w-10 text-center text-sm font-medium">
                          {item.quantity}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 rounded-l-none"
                          onClick={() =>
                            handleUpdateQuantity(
                              item.id,
                              item.listingId,
                              Math.min(
                                item.listing.stockQuantity,
                                item.quantity + 1,
                              ),
                            )
                          }
                          disabled={
                            item.quantity >= item.listing.stockQuantity ||
                            qtyBusy
                          }
                        >
                          <Plus className="w-3.5 h-3.5" />
                        </Button>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-foreground hidden sm:inline">
                          {formatTZS(
                            item.lineSubtotal ??
                              item.listing.price * item.quantity,
                          )}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20"
                          onClick={() => {
                            setItemToRemove(item.id);
                            setRemoveDialogOpen(true);
                          }}
                          disabled={isRemoving === item.id || qtyBusy}
                        >
                          {isRemoving === item.id ? (
                            <div className="w-4 h-4 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </Button>
                      </div>
                    </div>
                  </div>
                </motion.div>
              );
              })}
            </AnimatePresence>

            {/* Mobile Subtotal */}
            <div className="sm:hidden p-4 rounded-xl border bg-muted/30">
              <div className="flex justify-between text-sm mb-1">
                <span className="text-muted-foreground">Cart subtotal</span>
                <span className="font-medium">{formatTZS(serverCartTotal)}</span>
              </div>
              <p className="text-xs text-muted-foreground">
                Shipping and final total (including platform fees) are set at
                checkout from the server.
              </p>
            </div>
          </div>

          {/* Order Summary */}
          <Card className="h-fit sticky top-24 lg:sticky">
            <CardHeader>
              <CardTitle className="text-lg">Order Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">
                    Subtotal ({items.length}{' '}
                    {items.length === 1 ? 'item' : 'items'})
                  </span>
                  <span className="font-medium">{formatTZS(serverCartTotal)}</span>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Delivery and order total are finalized at checkout using server
                pricing.
              </p>
              <Separator />
              <Button
                className="w-full rounded-xl h-12 text-base font-semibold mt-2"
                onClick={() => router.push(routes.checkout())}
              >
                Proceed to Checkout
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
              <Button
                variant="ghost"
                className="w-full rounded-xl text-sm"
                onClick={() => router.push(routes.home())}
              >
                <ArrowLeft className="w-4 h-4 mr-1" />
                Continue Shopping
              </Button>
            </CardContent>
          </Card>
        </div>
      </motion.div>

      {/* Remove Dialog */}
      <Dialog open={removeDialogOpen} onOpenChange={setRemoveDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove Item</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove this item from your cart?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRemoveDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleConfirmRemove}>
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
