'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  CreditCard,
  Smartphone,
  Building2,
  ArrowLeft,
  Loader2,
  CheckCircle2,
  Wallet,
  Info,
  Shield,
} from 'lucide-react';
import { toast } from 'sonner';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import type { PaymentMethodOption, PaymentChannel } from '@/types/api';

// ─── Types ────────────────────────────────────────────────────────────────────

type PayoutMethodType = 'mobile_money' | 'bank_transfer';

const mobileMoneySchema = z.object({
  method: z.literal('mobile_money'),
  channel: z.string().min(1, 'Select a mobile money provider'),
  phone_number: z
    .string()
    .min(10, 'Phone number must be at least 10 digits')
    .regex(/^[0-9+\-\s]+$/, 'Enter a valid phone number'),
});

const bankTransferSchema = z.object({
  method: z.literal('bank_transfer'),
  bank_name: z.string().min(2, 'Enter a bank name'),
  account_number: z.string().min(5, 'Enter a valid account number'),
  account_name: z.string().min(2, 'Enter an account name'),
});

const payoutFormSchema = z.discriminatedUnion('method', [
  mobileMoneySchema,
  bankTransferSchema,
]);

type PayoutFormData = z.infer<typeof payoutFormSchema>;

// ─── Mobile Money Channels ────────────────────────────────────────────────────

const MOBILE_CHANNELS = [
  { id: 'm_pesa', name: 'M-Pesa', channel: 'm_pesa' as PaymentChannel },
  { id: 'tigo_pesa', name: 'Tigo Pesa', channel: 'tigo_pesa' as PaymentChannel },
  { id: 'airtel_money', name: 'Airtel Money', channel: 'airtel_money' as PaymentChannel },
  { id: 'halopesa', name: 'Halopesa', channel: 'halopesa' as PaymentChannel },
];

// ─── Component ─────────────────────────────────────────────────────────────────

export function SellerPaymentMethodPage() {
  const { navigate } = useUIStore();
  const { user, isAuthenticated } = useAuthStore();
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethodOption[]>([]);
  const [isLoadingMethods, setIsLoadingMethods] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [selectedMethod, setSelectedMethod] = useState<PayoutMethodType | null>(null);

  const sellerProfile = user?.seller_profile;
  const currentMethod = (sellerProfile?.payout_method as PayoutMethodType) || null;
  const currentDetails = sellerProfile?.payout_details as Record<string, unknown> | null;

  const form = useForm<PayoutFormData>({
    resolver: zodResolver(payoutFormSchema),
    // For discriminated unions, defaultValues must match ONE branch at a time.
    defaultValues: {
      method: 'mobile_money',
      channel: '',
      phone_number: '',
    } as any,
  });

  // ─── Auth guard ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) {
      navigate({ view: 'login' });
      return;
    }
    if (!user?.is_seller) {
      toast.error('You must be a seller to configure payout methods.');
      navigate({ view: 'seller-register' });
    }
  }, [isAuthenticated, user, navigate]);

  // ─── Load payment methods ──────────────────────────────────────────────────
  useEffect(() => {
    async function loadMethods() {
      try {
        const methods = await api.marketplace.paymentMethods();
        setPaymentMethods((methods as any) || []);
      } catch {
        // Use fallback channels if API fails
        setPaymentMethods([]);
      } finally {
        setIsLoadingMethods(false);
      }
    }
    loadMethods();
  }, []);

  // ─── Pre-populate form if existing method ──────────────────────────────────
  useEffect(() => {
    if (currentMethod && currentDetails) {
      setSelectedMethod(currentMethod);
      if (currentMethod === 'mobile_money') {
        form.setValue('method', 'mobile_money');
        form.setValue('channel', (currentDetails.channel as string) || '');
        form.setValue('phone_number', (currentDetails.phone_number as string) || '');
      } else if (currentMethod === 'bank_transfer') {
        form.setValue('method', 'bank_transfer');
        form.setValue('bank_name', (currentDetails.bank_name as string) || '');
        form.setValue('account_number', (currentDetails.account_number as string) || '');
        form.setValue('account_name', (currentDetails.account_name as string) || '');
      }
    }
  }, [currentMethod, currentDetails, form]);

  // ─── Submit ────────────────────────────────────────────────────────────────
  const onSubmit = async (data: PayoutFormData) => {
    setIsSaving(true);
    try {
      // Store payout preferences under marketplace payment-methods.
      // Backend syncs preferences into escrow_engine payout destination.
      const payoutDetails: Record<string, unknown> =
        data.method === 'mobile_money'
          ? { method: 'mobile_money', channel: data.channel, phone_number: data.phone_number }
          : {
              method: 'bank_transfer',
              bank_name: data.bank_name,
              account_number: data.account_number,
              account_name: data.account_name,
            };

      await api.marketplace.sellerPaymentMethods.create(payoutDetails);

      toast.success('Payout method updated successfully!');
      // Refresh user
      try {
        const updatedUser = await api.auth.me();
        useAuthStore.getState().setUser(updatedUser as any);
      } catch {
        // Non-critical
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update payout method.';
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  if (!isAuthenticated || !user) return null;

  const isConfigured = !!currentMethod;

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate({ view: 'seller-dashboard' })}
              className="shrink-0"
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
                Payout Method
              </h1>
              <p className="text-muted-foreground mt-1">
                Configure how you receive your earnings
              </p>
            </div>
          </div>
          {isConfigured && (
            <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Configured
            </Badge>
          )}
        </motion.div>

        {/* Current Method Card */}
        {isConfigured && currentMethod && currentDetails && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
          >
            <Card className="border-0 shadow-md shadow-black/5 bg-primary/5 dark:bg-primary/5">
              <CardContent className="p-5">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                    {currentMethod === 'mobile_money' ? (
                      <Smartphone className="w-5 h-5 text-primary" />
                    ) : (
                      <Building2 className="w-5 h-5 text-primary" />
                    )}
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-foreground">Current Payout Method</h3>
                    <p className="text-sm text-muted-foreground mt-0.5">
                      {currentMethod === 'mobile_money' ? 'Mobile Money' : 'Bank Transfer'}
                    </p>
                    <div className="mt-2 space-y-1">
                      {currentMethod === 'mobile_money' ? (
                        <>
                          <p className="text-sm text-foreground">
                            <span className="text-muted-foreground">Provider: </span>
                            {MOBILE_CHANNELS.find((c) => c.channel === currentDetails.channel)?.name || String(currentDetails.channel)}
                          </p>
                          <p className="text-sm text-foreground">
                            <span className="text-muted-foreground">Phone: </span>
                            {String(currentDetails.phone_number || '—')}
                          </p>
                        </>
                      ) : (
                        <>
                          <p className="text-sm text-foreground">
                            <span className="text-muted-foreground">Bank: </span>
                            {String(currentDetails.bank_name || '—')}
                          </p>
                          <p className="text-sm text-foreground">
                            <span className="text-muted-foreground">Account: </span>
                            {String(currentDetails.account_number || '—')}
                          </p>
                          <p className="text-sm text-foreground">
                            <span className="text-muted-foreground">Name: </span>
                            {String(currentDetails.account_name || '—')}
                          </p>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Method Selection */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg">Select Payout Method</CardTitle>
              <CardDescription>
                Choose how you want to receive your payouts
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {/* Mobile Money Option */}
                <button
                  type="button"
                  onClick={() => {
                    setSelectedMethod('mobile_money');
                    form.setValue('method', 'mobile_money');
                  }}
                  className={`
                    relative flex items-start gap-3 p-4 rounded-lg border-2 text-left transition-all
                    ${selectedMethod === 'mobile_money'
                      ? 'border-primary bg-primary/5'
                      : 'border-muted hover:border-primary/50'
                    }
                  `}
                >
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                    selectedMethod === 'mobile_money'
                      ? 'bg-primary/10'
                      : 'bg-muted'
                  }`}>
                    <Smartphone className={`w-5 h-5 ${
                      selectedMethod === 'mobile_money' ? 'text-primary' : 'text-muted-foreground'
                    }`} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">Mobile Money</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      M-Pesa, Tigo Pesa, Airtel Money, Halopesa
                    </p>
                  </div>
                  {selectedMethod === 'mobile_money' && (
                    <div className="absolute top-2 right-2">
                      <div className="w-5 h-5 rounded-full bg-primary flex items-center justify-center">
                        <CheckCircle2 className="w-3 h-3 text-primary-foreground" />
                      </div>
                    </div>
                  )}
                </button>

                {/* Bank Transfer Option */}
                <button
                  type="button"
                  onClick={() => {
                    setSelectedMethod('bank_transfer');
                    form.setValue('method', 'bank_transfer');
                  }}
                  className={`
                    relative flex items-start gap-3 p-4 rounded-lg border-2 text-left transition-all
                    ${selectedMethod === 'bank_transfer'
                      ? 'border-primary bg-primary/5'
                      : 'border-muted hover:border-primary/50'
                    }
                  `}
                >
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                    selectedMethod === 'bank_transfer'
                      ? 'bg-primary/10'
                      : 'bg-muted'
                  }`}>
                    <Building2 className={`w-5 h-5 ${
                      selectedMethod === 'bank_transfer' ? 'text-primary' : 'text-muted-foreground'
                    }`} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">Bank Transfer</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Direct transfer to your bank account
                    </p>
                  </div>
                  {selectedMethod === 'bank_transfer' && (
                    <div className="absolute top-2 right-2">
                      <div className="w-5 h-5 rounded-full bg-primary flex items-center justify-center">
                        <CheckCircle2 className="w-3 h-3 text-primary-foreground" />
                      </div>
                    </div>
                  )}
                </button>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Form Fields */}
        {selectedMethod && (
          <motion.div
            key={selectedMethod}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
          >
            <Card className="border-0 shadow-md shadow-black/5">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg">
                  {selectedMethod === 'mobile_money' ? 'Mobile Money Details' : 'Bank Account Details'}
                </CardTitle>
                <CardDescription>
                  {selectedMethod === 'mobile_money'
                    ? 'Enter your mobile money account details'
                    : 'Enter your bank account information'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                  {selectedMethod === 'mobile_money' && (
                    <>
                      {/* Provider Selection */}
                      <div className="space-y-2">
                        <Label>Mobile Money Provider *</Label>
                        {isLoadingMethods ? (
                          <Skeleton className="h-10 w-full" />
                        ) : (
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                            {MOBILE_CHANNELS.map((ch) => (
                              <button
                                key={ch.id}
                                type="button"
                                onClick={() => form.setValue('channel', ch.channel)}
                                className={`
                                  flex flex-col items-center gap-1.5 p-3 rounded-lg border-2 transition-all
                                  ${form.watch('channel') === ch.channel
                                    ? 'border-primary bg-primary/5'
                                    : 'border-muted hover:border-primary/50'
                                  }
                                `}
                              >
                                <Smartphone className={`w-5 h-5 ${
                                  form.watch('channel') === ch.channel ? 'text-primary' : 'text-muted-foreground'
                                }`} />
                                <span className={`text-xs font-medium ${
                                  form.watch('channel') === ch.channel ? 'text-primary' : 'text-muted-foreground'
                                }`}>
                                  {ch.name}
                                </span>
                              </button>
                            ))}
                          </div>
                        )}
                        {form.formState.errors.channel && (
                          <p className="text-xs text-destructive">{form.formState.errors.channel.message}</p>
                        )}
                      </div>

                      {/* Phone Number */}
                      <div className="space-y-2">
                        <Label htmlFor="phone_number">Phone Number *</Label>
                        <Input
                          id="phone_number"
                          placeholder="e.g. 255712345678"
                          {...form.register('phone_number')}
                          className={form.formState.errors.phone_number ? 'border-destructive' : ''}
                        />
                        {form.formState.errors.phone_number && (
                          <p className="text-xs text-destructive">{form.formState.errors.phone_number.message}</p>
                        )}
                      </div>
                    </>
                  )}

                  {selectedMethod === 'bank_transfer' && (
                    <>
                      {/* Bank Name */}
                      <div className="space-y-2">
                        <Label htmlFor="bank_name">Bank Name *</Label>
                        <Input
                          id="bank_name"
                          placeholder="e.g. CRDB, NMB, NBC"
                          {...form.register('bank_name')}
                          className={form.formState.errors.bank_name ? 'border-destructive' : ''}
                        />
                        {form.formState.errors.bank_name && (
                          <p className="text-xs text-destructive">{form.formState.errors.bank_name.message}</p>
                        )}
                      </div>

                      {/* Account Number */}
                      <div className="space-y-2">
                        <Label htmlFor="account_number">Account Number *</Label>
                        <Input
                          id="account_number"
                          placeholder="e.g. 0152345678900"
                          {...form.register('account_number')}
                          className={form.formState.errors.account_number ? 'border-destructive' : ''}
                        />
                        {form.formState.errors.account_number && (
                          <p className="text-xs text-destructive">{form.formState.errors.account_number.message}</p>
                        )}
                      </div>

                      {/* Account Name */}
                      <div className="space-y-2">
                        <Label htmlFor="account_name">Account Name *</Label>
                        <Input
                          id="account_name"
                          placeholder="e.g. John Doe"
                          {...form.register('account_name')}
                          className={form.formState.errors.account_name ? 'border-destructive' : ''}
                        />
                        {form.formState.errors.account_name && (
                          <p className="text-xs text-destructive">{form.formState.errors.account_name.message}</p>
                        )}
                      </div>
                    </>
                  )}

                  <Separator />

                  {/* Submit */}
                  <div className="flex justify-end">
                    <Button
                      type="submit"
                      disabled={isSaving}
                      className="gap-2 min-w-[140px]"
                    >
                      {isSaving ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Saving...
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="w-4 h-4" />
                          {isConfigured ? 'Update Method' : 'Save Method'}
                        </>
                      )}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Security Info */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
        >
          <Alert className="border-primary/20 bg-primary/5 dark:bg-primary/5">
            <Shield className="h-4 w-4 text-primary" />
            <AlertDescription className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">Secure & Encrypted: </span>
              Your payment information is encrypted and stored securely. We never share your financial details with third parties.
            </AlertDescription>
          </Alert>
        </motion.div>
      </div>
    </div>
  );
}
