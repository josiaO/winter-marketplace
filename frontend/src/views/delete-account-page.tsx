'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useRef, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Loader2,
  ShieldCheck,
  ArrowLeft,
  RefreshCw,
  Trash2,
  AlertTriangle,
  UserX,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { ApiClientError } from '@/lib/api-client';

const OTP_LENGTH = 6;
const RESEND_COOLDOWN = 60; // seconds

type Step = 'confirm' | 'otp' | 'deleting';

export function DeleteAccountPage() {
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuthStore();

  const [step, setStep] = useState<Step>('confirm');
  const [otp, setOtp] = useState<string[]>(Array(OTP_LENGTH).fill(''));
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      router.push(routes.login());
    }
  }, [isAuthenticated, router]);

  // Cooldown timer
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  // Auto-focus first OTP input
  useEffect(() => {
    if (step === 'otp') {
      setOtp(Array(OTP_LENGTH).fill(''));
      setTimeout(() => inputRefs.current[0]?.focus(), 100);
    }
  }, [step]);

  // --- OTP handlers ---

  const handleChange = useCallback((index: number, value: string) => {
    const digit = value.replace(/\D/g, '').slice(-1);
    setOtp((prev) => {
      const next = [...prev];
      next[index] = digit;
      return next;
    });
    if (digit && index < OTP_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }
  }, []);

  const handleKeyDown = useCallback(
    (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Backspace' && !otp[index] && index > 0) {
        inputRefs.current[index - 1]?.focus();
      }
      if (e.key === 'ArrowLeft' && index > 0) {
        inputRefs.current[index - 1]?.focus();
      }
      if (e.key === 'ArrowRight' && index < OTP_LENGTH - 1) {
        inputRefs.current[index + 1]?.focus();
      }
    },
    [otp],
  );

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, OTP_LENGTH);
    if (pasted.length === 0) return;
    const digits = pasted.split('');
    setOtp((prev) => {
      const next = [...prev];
      for (let i = 0; i < OTP_LENGTH; i++) {
        next[i] = digits[i] || '';
      }
      return next;
    });
    const focusIndex = Math.min(pasted.length, OTP_LENGTH - 1);
    inputRefs.current[focusIndex]?.focus();
  }, []);

  // --- Actions ---

  const handleRequestOtp = async () => {
    if (!user?.email) return;
    setError('');
    setIsLoading(true);

    try {
      await api.auth.requestOtp({ email: user.email });
      setStep('otp');
      setCooldown(RESEND_COOLDOWN);
      toast.success('A verification code has been sent to your email.');
    } catch (err: unknown) {
      let message = 'Failed to send verification code. Please try again.';
      if (err instanceof ApiClientError) {
        message = err.detail || err.message || message;
      } else if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (!user?.email || cooldown > 0) return;
    setIsLoading(true);
    setError('');

    try {
      await api.auth.requestOtp({ email: user.email });
      toast.success('A new verification code has been sent.');
      setCooldown(RESEND_COOLDOWN);
      setOtp(Array(OTP_LENGTH).fill(''));
      inputRefs.current[0]?.focus();
    } catch (err: unknown) {
      let message = 'Failed to resend code. Please try again.';
      if (err instanceof ApiClientError) {
        message = err.detail || err.message || message;
      } else if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmDelete = async () => {
    const otpValue = otp.join('');
    if (otpValue.length !== OTP_LENGTH) return;

    setError('');
    setStep('deleting');
    setIsLoading(true);

    try {
      // First verify OTP to authenticate the deletion
      await api.auth.verifyOtp({ email: user?.email || '', otp: otpValue });
      // Then delete the account
      await api.auth.deleteAccount();
      toast.success('Account deleted successfully.');
      logout();
      router.push(routes.home());
    } catch (err: unknown) {
      let message = 'Failed to delete account. Please try again.';
      if (err instanceof ApiClientError) {
        message = err.detail || err.message || message;
      } else if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
      toast.error(message);
      setStep('otp');
      setOtp(Array(OTP_LENGTH).fill(''));
      inputRefs.current[0]?.focus();
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    setStep('confirm');
    setOtp(Array(OTP_LENGTH).fill(''));
    setError('');
  };

  // Don't render if not authenticated
  if (!isAuthenticated || !user) {
    return null;
  }

  const otpValue = otp.join('');
  const isOtpComplete = otpValue.length === OTP_LENGTH;

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md"
      >
        {/* Header */}
        <div className="flex flex-col items-center mb-8">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, damping: 15, delay: 0.1 }}
            className="w-16 h-16 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center mb-4"
          >
            <UserX className="w-8 h-8 text-red-600" />
          </motion.div>
          <h1 className="text-xl font-bold text-foreground">Delete Account</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Permanently remove your account and all associated data.
          </p>
        </div>

        <Card className="border-0 shadow-xl shadow-black/5">
          <CardHeader className="pb-2 pt-6 px-6">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">Danger Zone</span>
              <button
                onClick={() => router.push(routes.profile())}
                className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                Back to Profile
              </button>
            </div>
          </CardHeader>
          <CardContent className="px-6 pb-6">
            <AnimatePresence mode="wait">
              {step === 'confirm' && (
                <motion.div
                  key="confirm"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  className="space-y-4"
                >
                  {/* Warning */}
                  <div className="bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800 rounded-lg p-4 space-y-3">
                    <div className="flex items-start gap-3">
                      <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5 shrink-0" />
                      <div className="text-sm text-red-800 dark:text-red-300 space-y-1.5">
                        <p className="font-semibold">This action cannot be undone!</p>
                        <p>Deleting your account will permanently remove:</p>
                        <ul className="list-disc list-inside space-y-0.5 text-red-700 dark:text-red-400">
                          <li>Your profile and personal information</li>
                          <li>All your listings and products</li>
                          <li>Order history and transaction records</li>
                          <li>Reviews and messages</li>
                          <li>Seller profile and store (if applicable)</li>
                        </ul>
                        <p className="mt-2">
                          Any active orders will be cancelled and pending payouts will be forfeited.
                        </p>
                      </div>
                    </div>
                  </div>

                  {error && (
                    <Alert variant="destructive" className="border-0">
                      <AlertDescription className="text-sm">{error}</AlertDescription>
                    </Alert>
                  )}

                  <div className="bg-muted/50 rounded-lg p-4">
                    <p className="text-sm text-muted-foreground">
                      Signed in as <span className="font-medium text-foreground">{user.email}</span>
                    </p>
                  </div>

                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button
                        variant="destructive"
                        className="w-full h-11 text-sm font-semibold"
                        disabled={isLoading}
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Delete My Account
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                        <AlertDialogDescription>
                          This will permanently delete your account and remove all your data from our
                          servers. This action cannot be undone.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={handleRequestOtp}
                          className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
                        >
                          Yes, send verification code
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </motion.div>
              )}

              {step === 'otp' && (
                <motion.div
                  key="otp"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  className="space-y-6"
                >
                  <div className="text-center space-y-2">
                    <div className="mx-auto w-12 h-12 bg-emerald-100 dark:bg-emerald-900/30 rounded-full flex items-center justify-center">
                      <ShieldCheck className="w-6 h-6 text-emerald-600" />
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Enter the 6-digit code sent to{' '}
                      <span className="font-medium text-foreground">{user?.email}</span>
                    </p>
                  </div>

                  {error && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                    >
                      <Alert variant="destructive" className="border-0">
                        <AlertDescription className="text-sm">{error}</AlertDescription>
                      </Alert>
                    </motion.div>
                  )}

                  {/* OTP Input */}
                  <div className="flex justify-center gap-2 sm:gap-3">
                    {Array.from({ length: OTP_LENGTH }).map((_, index) => (
                      <Input
                        key={index}
                        ref={(el) => {
                          inputRefs.current[index] = el;
                        }}
                        type="text"
                        inputMode="numeric"
                        maxLength={1}
                        autoComplete="one-time-code"
                        value={otp[index]}
                        onChange={(e) => handleChange(index, e.target.value)}
                        onKeyDown={(e) => handleKeyDown(index, e)}
                        onPaste={index === 0 ? handlePaste : undefined}
                        className={`w-11 h-14 text-center text-xl font-bold sm:w-12 sm:h-16 sm:text-2xl transition-all ${
                          otp[index]
                            ? 'border-emerald-500 ring-2 ring-emerald-500/20 bg-emerald-50 dark:bg-emerald-950/30'
                            : 'focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20'
                        }`}
                        disabled={isLoading}
                      />
                    ))}
                  </div>

                  {/* Resend */}
                  <div className="text-sm text-center">
                    {cooldown > 0 ? (
                      <span className="text-muted-foreground">
                        Resend code in{' '}
                        <span className="font-semibold text-foreground">{cooldown}s</span>
                      </span>
                    ) : (
                      <button
                        onClick={handleResendOtp}
                        disabled={isLoading}
                        className="text-emerald-600 hover:text-emerald-700 font-semibold hover:underline disabled:opacity-50 inline-flex items-center gap-1.5"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                        Resend code
                      </button>
                    )}
                  </div>

                  <Separator />

                  <div className="flex gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleCancel}
                      className="flex-1 h-11"
                      disabled={isLoading}
                    >
                      Cancel
                    </Button>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="destructive"
                          className="flex-1 h-11"
                          disabled={!isOtpComplete || isLoading}
                        >
                          {isLoading ? (
                            <>
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                              Deleting...
                            </>
                          ) : (
                            <>
                              <Trash2 className="w-4 h-4 mr-2" />
                              Confirm Delete
                            </>
                          )}
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Final Confirmation</AlertDialogTitle>
                          <AlertDialogDescription>
                            Your account and all associated data will be permanently deleted. This
                            includes your listings, orders, reviews, and messages. You will be
                            immediately logged out.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={handleConfirmDelete}
                            className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
                          >
                            Permanently Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </motion.div>
              )}

              {step === 'deleting' && (
                <motion.div
                  key="deleting"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center py-12 space-y-4"
                >
                  <Loader2 className="w-10 h-10 text-red-600 animate-spin" />
                  <p className="text-sm text-muted-foreground">Deleting your account...</p>
                  <p className="text-xs text-muted-foreground">
                    This may take a few moments.
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
