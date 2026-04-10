'use client';

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Store,
  Building2,
  MapPin,
  Landmark,
  CreditCard,
  FileText,
  Check,
  ArrowRight,
  ArrowLeft,
  Loader2,
  Globe,
  Shield,
  TrendingUp,
  Wallet,
  Users,
  ChevronRight,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { useUIStore, useAuthStore } from '@/store';
import { canAccessSellerPortal } from '@/lib/auth-roles';
import { api } from '@/lib/api-client';
import type { BecomeSellerPayload } from '@/types/api';

interface SellerFormValues {
  businessName: string;
  businessAddress: string;
  bankName: string;
  bankAccount: string;
  bio: string;
}

const STEPS = [
  { id: 1, title: 'Business Info', icon: Building2 },
  { id: 2, title: 'Payment Info', icon: CreditCard },
  { id: 3, title: 'Start Selling', icon: Store },
];

const BENEFITS = [
  {
    icon: Globe,
    title: 'Reach Millions',
    description: 'Access thousands of buyers across Tanzania looking for products like yours.',
  },
  {
    icon: Shield,
    title: 'Secure Payments',
    description: 'All payments are held in escrow until delivery is confirmed, protecting both parties.',
  },
  {
    icon: TrendingUp,
    title: 'Seller Tools',
    description: 'Powerful dashboard, order management, analytics, and listing tools at your fingertips.',
  },
  {
    icon: Wallet,
    title: 'Low Commissions',
    description: 'Competitive commission rates so you keep more of your earnings from each sale.',
  },
];

export function SellerRegisterPage() {
  const { navigate } = useUIStore();
  const { user, isAuthenticated, setUser } = useAuthStore();
  const [currentStep, setCurrentStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const {
    register,
    handleSubmit,
    formState: { errors },
    trigger,
    watch,
  } = useForm<SellerFormValues>({
    defaultValues: {
      businessName: '',
      businessAddress: '',
      bankName: '',
      bankAccount: '',
      bio: '',
    },
  });

  const watchedValues = watch();

  // Auth check
  useEffect(() => {
    if (!isAuthenticated) {
      navigate({ view: 'login' });
    }
  }, [isAuthenticated, navigate]);

  // Already seller check (matches backend IsSeller)
  useEffect(() => {
    if (user && canAccessSellerPortal(user)) {
      toast.info('You are already registered as a seller!');
      navigate({ view: 'seller-dashboard' });
    }
  }, [user, navigate]);

  const validateStep = async (step: number): Promise<boolean> => {
    switch (step) {
      case 1:
        return trigger(['businessName', 'businessAddress']);
      case 2:
        return trigger(['bankName', 'bankAccount']);
      default:
        return true;
    }
  };

  const handleNext = async () => {
    const valid = await validateStep(currentStep);
    if (valid) {
      setCurrentStep((prev) => Math.min(prev + 1, 3));
      setError('');
    }
  };

  const handleBack = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1));
    setError('');
  };

  const onSubmit = async (data: SellerFormValues) => {
    if (!user) return;
    setError('');
    setIsLoading(true);
    try {
      // Backend "become seller" upgrades the role and returns fresh JWTs.
      const res = await api.auth.becomeSeller();
      api.setTokens(res.access, res.refresh);

      // Store setup (sellers onboarding)
      await api.sellers.storeSetup({
        store_name: data.businessName,
        // If we don't collect categories yet, default to Other.
        store_category: 'other',
        store_category_other: 'General goods',
        store_location: data.businessAddress,
        store_description: data.bio,
      });

      const me = await api.auth.me();
      setUser(me as any);
      toast.success('Seller account created. Next: verify your identity.');
      navigate({ view: 'seller-verification' });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to register as seller.';
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isAuthenticated || !user) return null;

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary/10 rounded-2xl mb-4">
            <Store className="w-8 h-8 text-primary" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-2">
            Become a Seller
          </h1>
          <p className="text-muted-foreground max-w-md mx-auto">
            Join Tanzania&apos;s growing marketplace and start selling to thousands of buyers today.
          </p>
        </motion.div>

        {/* Step Indicators */}
        <div className="flex items-center justify-center gap-2 sm:gap-4 mb-8">
          {STEPS.map((step, index) => {
            const isCompleted = currentStep > step.id;
            const isActive = currentStep === step.id;
            return (
              <div key={step.id} className="flex items-center">
                <div className="flex flex-col items-center gap-1.5">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-300 ${
                      isCompleted
                        ? 'bg-primary text-primary-foreground'
                        : isActive
                          ? 'bg-primary text-primary-foreground ring-4 ring-primary/20'
                          : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {isCompleted ? <Check className="w-5 h-5" /> : step.id}
                  </div>
                  <span
                    className={`text-xs font-medium hidden sm:block ${
                      isActive || isCompleted
                        ? 'text-primary'
                        : 'text-muted-foreground'
                    }`}
                  >
                    {step.title}
                  </span>
                </div>
                {index < STEPS.length - 1 && (
                  <ChevronRight className="w-4 h-4 text-muted-foreground mx-1 sm:mx-3 hidden sm:block" />
                )}
              </div>
            );
          })}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Form */}
          <div className="lg:col-span-2">
            <motion.div
              key={currentStep}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3 }}
            >
              <Card className="border-0 shadow-lg shadow-black/5">
                <CardHeader className="pb-4">
                  <CardTitle className="text-lg">
                    {currentStep === 1 && 'Business Information'}
                    {currentStep === 2 && 'Payment Details'}
                    {currentStep === 3 && 'Review & Start Selling'}
                  </CardTitle>
                  <CardDescription>
                    {currentStep === 1 && 'Tell us about your business'}
                    {currentStep === 2 && 'Where should we send your payouts?'}
                    {currentStep === 3 && 'Review your seller profile before submitting'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
                    {error && (
                      <Alert variant="destructive" className="border-0">
                        <AlertDescription className="text-sm">{error}</AlertDescription>
                      </Alert>
                    )}

                    {/* Step 1: Business Info */}
                    <AnimatePresence mode="wait">
                      {currentStep === 1 && (
                        <motion.div
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="space-y-4"
                        >
                          <div className="space-y-2">
                            <Label htmlFor="businessName" className="text-sm font-medium">
                              Business Name <span className="text-destructive">*</span>
                            </Label>
                            <div className="relative">
                              <Building2 className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                              <Input
                                id="businessName"
                                placeholder="e.g., DarTech Electronics"
                                className="pl-10 h-11"
                                {...register('businessName', {
                                  required: 'Business name is required',
                                  minLength: { value: 2, message: 'Name must be at least 2 characters' },
                                })}
                              />
                            </div>
                            {errors.businessName && (
                              <p className="text-xs text-destructive">{errors.businessName.message}</p>
                            )}
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="businessAddress" className="text-sm font-medium">
                              Business Address <span className="text-destructive">*</span>
                            </Label>
                            <div className="relative">
                              <MapPin className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                              <Input
                                id="businessAddress"
                                placeholder="e.g., Kijitonyama, Dar es Salaam"
                                className="pl-10 h-11"
                                {...register('businessAddress', {
                                  required: 'Business address is required',
                                })}
                              />
                            </div>
                            {errors.businessAddress && (
                              <p className="text-xs text-destructive">{errors.businessAddress.message}</p>
                            )}
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="bio" className="text-sm font-medium">
                              Bio / Description
                            </Label>
                            <div className="relative">
                              <FileText className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                              <Textarea
                                id="bio"
                                placeholder="Tell buyers about your business, what you sell, and why they should trust you..."
                                className="pl-10 min-h-[100px] resize-none"
                                {...register('bio')}
                              />
                            </div>
                          </div>
                        </motion.div>
                      )}

                      {/* Step 2: Payment Info */}
                      {currentStep === 2 && (
                        <motion.div
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="space-y-4"
                        >
                          <div className="space-y-2">
                            <Label htmlFor="bankName" className="text-sm font-medium">
                              Bank Name <span className="text-destructive">*</span>
                            </Label>
                            <div className="relative">
                              <Landmark className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                              <Input
                                id="bankName"
                                placeholder="e.g., CRDB, NMB, NBC"
                                className="pl-10 h-11"
                                {...register('bankName', {
                                  required: 'Bank name is required',
                                })}
                              />
                            </div>
                            {errors.bankName && (
                              <p className="text-xs text-destructive">{errors.bankName.message}</p>
                            )}
                          </div>

                          <div className="space-y-2">
                            <Label htmlFor="bankAccount" className="text-sm font-medium">
                              Bank Account Number <span className="text-destructive">*</span>
                            </Label>
                            <div className="relative">
                              <CreditCard className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                              <Input
                                id="bankAccount"
                                placeholder="Enter your bank account number"
                                className="pl-10 h-11"
                                {...register('bankAccount', {
                                  required: 'Bank account number is required',
                                  minLength: { value: 6, message: 'Please enter a valid account number' },
                                })}
                              />
                            </div>
                            {errors.bankAccount && (
                              <p className="text-xs text-destructive">{errors.bankAccount.message}</p>
                            )}
                          </div>

                          <Alert className="bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800">
                            <AlertDescription className="text-xs text-amber-800 dark:text-amber-300">
                              Your payment information is encrypted and stored securely. Payouts are released
                              48 hours after delivery confirmation.
                            </AlertDescription>
                          </Alert>
                        </motion.div>
                      )}

                      {/* Step 3: Preview */}
                      {currentStep === 3 && (
                        <motion.div
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="space-y-4"
                        >
                          <div className="rounded-xl border bg-muted/30 p-4 space-y-3">
                            <div className="flex items-center gap-3">
                              <div className="w-12 h-12 bg-primary rounded-xl flex items-center justify-center">
                                <Store className="w-6 h-6 text-primary-foreground" />
                              </div>
                              <div>
                                <h3 className="font-semibold text-foreground">
                                  {watchedValues.businessName || 'Business Name'}
                                </h3>
                                <p className="text-sm text-muted-foreground">
                                  {watchedValues.businessAddress || 'Address not set'}
                                </p>
                              </div>
                            </div>
                            {watchedValues.bio && (
                              <p className="text-sm text-muted-foreground leading-relaxed">
                                {watchedValues.bio}
                              </p>
                            )}
                            <Separator />
                            <div className="grid grid-cols-2 gap-3 text-sm">
                              <div>
                                <span className="text-muted-foreground">Bank:</span>{' '}
                                <span className="font-medium text-foreground">
                                  {watchedValues.bankName || 'Not set'}
                                </span>
                              </div>
                              <div>
                                <span className="text-muted-foreground">Account:</span>{' '}
                                <span className="font-medium text-foreground">
                                  {watchedValues.bankAccount
                                    ? `****${watchedValues.bankAccount.slice(-4)}`
                                    : 'Not set'}
                                </span>
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {/* Navigation Buttons */}
                    <div className="flex justify-between pt-4">
                      {currentStep > 1 ? (
                        <Button
                          type="button"
                          variant="outline"
                          onClick={handleBack}
                          className="gap-2"
                        >
                          <ArrowLeft className="w-4 h-4" />
                          Back
                        </Button>
                      ) : (
                        <div />
                      )}

                      {currentStep < 3 ? (
                        <Button
                          type="button"
                          onClick={handleNext}
                          className="gap-2"
                        >
                          Next
                          <ArrowRight className="w-4 h-4" />
                        </Button>
                      ) : (
                        <Button
                          type="submit"
                          disabled={isLoading}
                          className="gap-2"
                        >
                          {isLoading ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" />
                              Registering...
                            </>
                          ) : (
                            <>
                              Register as Seller
                              <Check className="w-4 h-4" />
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                  </form>
                </CardContent>
              </Card>
            </motion.div>
          </div>

          {/* Benefits Sidebar */}
          <div className="space-y-4">
            <h3 className="font-semibold text-foreground flex items-center gap-2">
              <Users className="w-4 h-4 text-primary" />
              Why Sell on SmartDalali?
            </h3>
            {BENEFITS.map((benefit, index) => (
              <motion.div
                key={benefit.title}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 * index, duration: 0.3 }}
              >
                <Card className="border-0 shadow-sm hover:shadow-md transition-shadow">
                  <CardContent className="p-4">
                    <div className="flex gap-3">
                      <div className="w-9 h-9 bg-primary/10 rounded-lg flex items-center justify-center shrink-0">
                        <benefit.icon className="w-4 h-4 text-primary" />
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-foreground">
                          {benefit.title}
                        </h4>
                        <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                          {benefit.description}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
