'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  CreditCard,
  Smartphone,
  Truck,
  Zap,
  Loader2,
  Check,
  Package as PickupIcon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS } from '@/lib/helpers';
import { toast } from 'sonner';
import type {
  Cart as DjangoCart,
  CheckoutPayload,
  Listing,
  ShippingMethod,
  PaymentMethod,
  PaymentChannel,
  Order,
  ShippingOptionRow,
} from '@/types/api';

/** Sum seller-defined delivery fees on cart lines (matches checkout OrderService). */
function listingDeliveryFromCart(cart: DjangoCart | null): number {
  if (!cart?.items?.length) return 0;
  let total = 0;
  for (const it of cart.items) {
    const l = it.listing as Listing;
    if (l.delivery_is_free !== false) continue;
    const fee = Number(l.delivery_fee ?? 0);
    if (fee <= 0) continue;
    total += fee * it.quantity;
  }
  return total;
}

// ---------------------------------------------------------------------------
// Payment-method value → Django enum mapping
// ---------------------------------------------------------------------------

const PAYMENT_METHODS: Array<{
  value: string;
  label: string;
  description: string;
  icon: typeof Smartphone;
  djangoMethod: PaymentMethod;
  djangoChannel?: PaymentChannel;
}> = [
  {
    value: 'm_pesa',
    label: 'M-Pesa',
    description: 'Mobile money',
    icon: Smartphone,
    djangoMethod: 'mobile_money',
    djangoChannel: 'm_pesa',
  },
  {
    value: 'tigo_pesa',
    label: 'Tigo Pesa',
    description: 'Mobile money',
    icon: Smartphone,
    djangoMethod: 'mobile_money',
    djangoChannel: 'tigo_pesa',
  },
  {
    value: 'airtel_money',
    label: 'Airtel Money',
    description: 'Mobile money',
    icon: Smartphone,
    djangoMethod: 'mobile_money',
    djangoChannel: 'airtel_money',
  },
  {
    value: 'card',
    label: 'Card Payment',
    description: 'Visa / Mastercard',
    icon: CreditCard,
    djangoMethod: 'card',
  },
];

function getPaymentEnums(value: string): {
  method: PaymentMethod;
  channel?: PaymentChannel;
} {
  const found = PAYMENT_METHODS.find((m) => m.value === value);
  return found
    ? { method: found.djangoMethod, channel: found.djangoChannel }
    : { method: 'mobile_money', channel: 'm_pesa' };
}

// ---------------------------------------------------------------------------

function ShipMethodIcon({ method }: { method: string }) {
  if (method === 'express')
    return <Zap className="w-4 h-4 text-amber-500" />;
  if (method === 'pickup')
    return <PickupIcon className="w-4 h-4 text-muted-foreground" />;
  return <Truck className="w-4 h-4 text-muted-foreground" />;
}

interface FormErrors {
  address?: string;
  phone?: string;
  terms?: string;
}

export function CheckoutPage() {
  const { navigate } = useUIStore();
  const { isAuthenticated, user } = useAuthStore();

  const [cartData, setCartData] = useState<DjangoCart | null>(null);
  const [shippingOptionRows, setShippingOptionRows] = useState<
    ShippingOptionRow[]
  >([]);
  const [cartLoadError, setCartLoadError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [address, setAddress] = useState(user?.profile?.address || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [shippingMethod, setShippingMethod] = useState('standard');
  const [paymentMethod, setPaymentMethod] = useState('m_pesa');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      navigate({ view: 'login' });
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    if (!isAuthenticated) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setCartLoadError(false);
    Promise.all([api.commerce.cart(), api.commerce.shippingOptions()])
      .then(([cart, ship]) => {
        setCartData(cart);
        setShippingOptionRows(ship.options ?? []);
      })
      .catch(() => {
        setCartLoadError(true);
        toast.error('Failed to load cart or shipping options');
      })
      .finally(() => setIsLoading(false));
  }, [isAuthenticated]);

  useEffect(() => {
    if (shippingOptionRows.length === 0) return;
    setShippingMethod((m) =>
      shippingOptionRows.some((o) => o.method === m)
        ? m
        : shippingOptionRows[0].method,
    );
  }, [shippingOptionRows]);

  const items = cartData?.items || [];
  const cartSubtotalServer = cartData ? Number(cartData.total) : 0;
  const shippingRow = shippingOptionRows.find((s) => s.method === shippingMethod);
  const platformShippingFee = shippingRow ? Number(shippingRow.fee) : 0;
  const listingDeliveryTotal = listingDeliveryFromCart(cartData);
  const shippingSummaryAmount =
    listingDeliveryTotal > 0 ? listingDeliveryTotal : platformShippingFee;

  const validate = (): boolean => {
    const newErrors: FormErrors = {};
    if (!address.trim()) newErrors.address = 'Shipping address is required';
    if (!phone.trim()) newErrors.phone = 'Phone number is required';
    else if (phone.length < 9) newErrors.phone = 'Enter a valid phone number';
    if (!termsAccepted)
      newErrors.terms = 'You must accept the terms and conditions';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!isAuthenticated || !user) return;
    if (!validate()) return;
    if (items.length === 0) {
      toast.error('Your cart is empty');
      return;
    }

    setIsSubmitting(true);
    try {
      const { method, channel } = getPaymentEnums(paymentMethod);
      const origin =
        typeof window !== 'undefined' ? window.location.origin : '';

      const payload: CheckoutPayload = {
        shipping_address: address,
        shipping_phone: phone,
        shipping_method: shippingMethod as ShippingMethod,
        payment_method: method,
        ...(channel ? { payment_channel: channel } : {}),
        ...(origin
          ? { redirect_url: `${origin}/`, cancel_url: `${origin}/` }
          : {}),
      };

      const raw = await api.commerce.checkout(payload);
      const orders: Order[] = Array.isArray(raw) ? raw : [raw as Order];
      const primary = orders[0] as Order & {
        payment_url?: string;
        transaction_reference?: string;
      };

      if (primary.payment_url) {
        if (primary.transaction_reference && typeof sessionStorage !== 'undefined') {
          try {
            sessionStorage.setItem(
              'sd_pending_txn_ref',
              primary.transaction_reference,
            );
          } catch {
            /* ignore quota / private mode */
          }
        }
        window.location.assign(primary.payment_url);
        return;
      }

      if (orders.length > 1) {
        toast.success(`Orders placed successfully! (${orders.length} orders)`);
        navigate({ view: 'orders' });
      } else {
        toast.success('Order placed successfully!');
        navigate({ view: 'checkout-success', orderId: String(primary.id) });
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to place order';
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isAuthenticated || !user) return null;

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-8 w-48 mb-6" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-4">
            <Skeleton className="h-40 rounded-xl" />
            <Skeleton className="h-40 rounded-xl" />
          </div>
          <Skeleton className="h-64 rounded-xl" />
        </div>
      </div>
    );
  }

  if (cartLoadError || !cartData) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 text-center">
        <p className="text-muted-foreground mb-4">Could not load your cart.</p>
        <Button onClick={() => navigate({ view: 'cart' })}>Back to cart</Button>
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
          Checkout
        </h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Checkout Form */}
          <div className="lg:col-span-2 space-y-6">
            {/* Shipping Address */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Truck className="w-4 h-4" />
                  Shipping Address
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="address">Delivery Address</Label>
                  <Textarea
                    id="address"
                    placeholder="Enter your full delivery address (street, city, region)"
                    value={address}
                    onChange={(e) => {
                      setAddress(e.target.value);
                      if (errors.address)
                        setErrors((prev) => ({ ...prev, address: undefined }));
                    }}
                    rows={3}
                    className={errors.address ? 'border-red-500' : ''}
                  />
                  {errors.address && (
                    <p className="text-xs text-red-500">{errors.address}</p>
                  )}
                </div>
                <div className="space-y-2">
                  <Label htmlFor="phone">Phone Number</Label>
                  <Input
                    id="phone"
                    placeholder="e.g. 0712345678"
                    value={phone}
                    onChange={(e) => {
                      setPhone(e.target.value);
                      if (errors.phone)
                        setErrors((prev) => ({ ...prev, phone: undefined }));
                    }}
                    className={errors.phone ? 'border-red-500' : ''}
                  />
                  {errors.phone && (
                    <p className="text-xs text-red-500">{errors.phone}</p>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Shipping Method */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Truck className="w-4 h-4" />
                  Shipping Method
                </CardTitle>
              </CardHeader>
              <CardContent>
                <RadioGroup
                  value={shippingMethod}
                  onValueChange={setShippingMethod}
                  className="space-y-3"
                >
                  {shippingOptionRows.map((option) => (
                    <label
                      key={option.method}
                      className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                        shippingMethod === option.method
                          ? 'border-primary bg-primary/5'
                          : 'hover:border-muted-foreground/30'
                      }`}
                    >
                      <RadioGroupItem
                        value={option.method}
                        id={`ship-${option.method}`}
                      />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <ShipMethodIcon method={option.method} />
                          <span className="text-sm font-medium">
                            {option.label}
                          </span>
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {option.description}
                        </span>
                      </div>
                      <span className="text-sm font-semibold">
                        {formatTZS(Number(option.fee))}
                      </span>
                    </label>
                  ))}
                </RadioGroup>
              </CardContent>
            </Card>

            {/* Payment Method */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <CreditCard className="w-4 h-4" />
                  Payment Method
                </CardTitle>
              </CardHeader>
              <CardContent>
                <RadioGroup
                  value={paymentMethod}
                  onValueChange={setPaymentMethod}
                  className="space-y-3"
                >
                  {PAYMENT_METHODS.map((method) => (
                    <label
                      key={method.value}
                      className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                        paymentMethod === method.value
                          ? 'border-primary bg-primary/5'
                          : 'hover:border-muted-foreground/30'
                      }`}
                    >
                      <RadioGroupItem
                        value={method.value}
                        id={`pay-${method.value}`}
                      />
                      <method.icon className="w-4 h-4 text-muted-foreground" />
                      <div className="flex-1">
                        <span className="text-sm font-medium">
                          {method.label}
                        </span>
                        <p className="text-xs text-muted-foreground">
                          {method.description}
                        </p>
                      </div>
                    </label>
                  ))}
                </RadioGroup>
              </CardContent>
            </Card>

            {/* Terms */}
            <div className="flex items-start gap-3">
              <Checkbox
                id="terms"
                checked={termsAccepted}
                onCheckedChange={(checked) => {
                  setTermsAccepted(checked === true);
                  if (errors.terms)
                    setErrors((prev) => ({ ...prev, terms: undefined }));
                }}
                className="mt-0.5"
              />
              <div>
                <Label htmlFor="terms" className="text-sm cursor-pointer">
                  I agree to the{' '}
                  <span className="text-primary underline cursor-pointer">
                    Terms and Conditions
                  </span>{' '}
                  and{' '}
                  <span className="text-primary underline cursor-pointer">
                    Privacy Policy
                  </span>
                </Label>
                {errors.terms && (
                  <p className="text-xs text-red-500 mt-1">{errors.terms}</p>
                )}
              </div>
            </div>
          </div>

          {/* Order Summary */}
          <Card className="h-fit sticky top-24">
            <CardHeader>
              <CardTitle className="text-lg">Order Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Items */}
              <div className="space-y-3 max-h-64 overflow-y-auto">
                {items.map((item) => (
                  <div key={item.id} className="flex gap-3">
                    <div className="relative w-12 h-12 rounded-lg overflow-hidden bg-muted flex-shrink-0">
                      {item.listing.images?.[0]?.url || item.listing.image ? (
                        <img
                          src={
                            item.listing.images?.[0]?.url ||
                            item.listing.image ||
                            ''
                          }
                          alt={item.listing.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <Package className="w-4 h-4 text-muted-foreground/30" />
                        </div>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-foreground line-clamp-1">
                        {item.listing.title}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Qty: {item.quantity}
                      </p>
                    </div>
                    <span className="text-sm font-medium flex-shrink-0">
                      {formatTZS(
                        item.subtotal != null
                          ? Number(item.subtotal)
                          : Number(item.listing.price) * item.quantity,
                      )}
                    </span>
                  </div>
                ))}
              </div>

              <Separator />

              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">
                    Subtotal (from server)
                  </span>
                  <span className="font-medium">
                    {formatTZS(cartSubtotalServer)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">
                    {listingDeliveryTotal > 0
                      ? 'Delivery (from your items × qty)'
                      : `Delivery — ${shippingRow?.label ?? shippingMethod} (platform)`}
                  </span>
                  <span className="font-medium">
                    {formatTZS(shippingSummaryAmount)}
                  </span>
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                When sellers charge delivery on their listings, that amount is
                used instead of the platform grid. Order total still includes
                platform fees from the server; the payment gateway shows the
                final charge.
              </p>
              <Separator />

              <Button
                className="w-full rounded-xl h-12 text-base font-semibold mt-2"
                onClick={handleSubmit}
                disabled={isSubmitting || items.length === 0}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Placing Order...
                  </>
                ) : (
                  <>
                    <Check className="w-4 h-4 mr-2" />
                    Place Order
                  </>
                )}
              </Button>
            </CardContent>
          </Card>
        </div>
      </motion.div>
    </div>
  );
}

function Package({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M16.5 9.4 7.55 4.24" />
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.29 7 12 12 20.71 7" />
      <line x1="12" x2="12" y1="22" y2="12" />
    </svg>
  );
}
