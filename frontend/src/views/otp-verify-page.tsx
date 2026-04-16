'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  ShoppingBag,
  Loader2,
  Mail,
  ShieldCheck,
  ArrowLeft,
  RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/store';
import { getPostLoginPath } from '@/lib/auth-roles';
import { routes } from '@/lib/routes';
import type { User } from '@/types/api';
import { api } from '@/lib/api-client';
import { ApiClientError } from '@/lib/api-client';

const OTP_LENGTH = 6;
const RESEND_COOLDOWN = 60; // seconds

export function OtpVerifyPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const email = (searchParams.get('email') || '').trim();
  const { isAuthenticated, user: authUser } = useAuthStore();

  useEffect(() => {
    if (isAuthenticated) {
      router.replace(getPostLoginPath(authUser));
    }
  }, [isAuthenticated, authUser, router]);
  const [otp, setOtp] = useState<string[]>(Array(OTP_LENGTH).fill(''));
  const [isLoading, setIsLoading] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const [error, setError] = useState('');
  const [cooldown, setCooldown] = useState(0);

  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Cooldown timer
  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  // Auto-focus first input on mount
  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  const handleChange = useCallback(
    (index: number, value: string) => {
      // Only allow digits
      const digit = value.replace(/\D/g, '').slice(-1);

      setOtp((prev) => {
        const next = [...prev];
        next[index] = digit;
        return next;
      });

      // Auto-advance to next input
      if (digit && index < OTP_LENGTH - 1) {
        inputRefs.current[index + 1]?.focus();
      }
    },
    [],
  );

  const handleKeyDown = useCallback(
    (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Backspace' && !otp[index] && index > 0) {
        // Move to previous input on backspace if current is empty
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

    // Focus the input after the last pasted digit
    const focusIndex = Math.min(pasted.length, OTP_LENGTH - 1);
    inputRefs.current[focusIndex]?.focus();
  }, []);

  const otpValue = otp.join('');
  const isComplete = otpValue.length === OTP_LENGTH;

  const handleVerify = async () => {
    if (!isComplete || !email) return;
    setError('');
    setIsLoading(true);

    try {
      const result = await api.auth.verifyOtp({
        email,
        code: otpValue,
      });
      api.setTokens(result.access, result.refresh);
      let profile: User | null = null;
      try {
        profile = (await api.auth.me()) as User;
        useAuthStore.setState({
          user: profile,
          isAuthenticated: true,
        });
      } catch {
        toast.error('Verified, but we could not load your profile. Try signing in.');
        router.replace(routes.login());
        return;
      }
      toast.success('Email verified successfully! Welcome to SmartDalali.');
      router.replace(getPostLoginPath(profile));
    } catch (err: unknown) {
      let message = 'Verification failed. Please check your OTP and try again.';
      if (err instanceof ApiClientError) {
        message = err.detail || err.message || message;
      } else if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
      toast.error(message);
      // Clear OTP on error
      setOtp(Array(OTP_LENGTH).fill(''));
      inputRefs.current[0]?.focus();
    } finally {
      setIsLoading(false);
    }
  };

  const handleResend = async () => {
    if (!email || cooldown > 0) return;
    setIsResending(true);
    setError('');

    try {
      await api.auth.requestOtp({ email });
      toast.success('A new OTP has been sent to your email.');
      setCooldown(RESEND_COOLDOWN);
      setOtp(Array(OTP_LENGTH).fill(''));
      inputRefs.current[0]?.focus();
    } catch (err: unknown) {
      let message = 'Failed to resend OTP. Please try again.';
      if (err instanceof ApiClientError) {
        message = err.detail || err.message || message;
      } else if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
      toast.error(message);
    } finally {
      setIsResending(false);
    }
  };

  // Guard: if no email, redirect to login
  if (!email) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
        <Card className="border-0 shadow-xl shadow-black/5 w-full max-w-md">
          <CardContent className="p-6 text-center space-y-4">
            <p className="text-muted-foreground">No email address provided for verification.</p>
            <Button
              variant="outline"
              onClick={() => router.push(routes.login())}
              className="bg-emerald-600 hover:bg-emerald-700 text-white border-0"
            >
              Go to Login
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="w-full max-w-md"
      >
        {/* Brand Logo */}
        <div className="flex flex-col items-center mb-8">
          <button
            onClick={() => router.push(routes.home())}
            className="flex items-center gap-3 group mb-2"
          >
            <div className="w-12 h-12 bg-emerald-600 rounded-2xl flex items-center justify-center shadow-lg shadow-emerald-600/20 group-hover:scale-105 transition-transform">
              <ShoppingBag className="w-7 h-7 text-white" />
            </div>
            <div>
              <span className="text-2xl font-bold text-foreground tracking-tight">
                Smart<span className="text-emerald-600">Dalali</span>
              </span>
            </div>
          </button>
        </div>

        {/* OTP Card */}
        <Card className="border-0 shadow-xl shadow-black/5">
          <CardHeader className="text-center pb-2 pt-6 px-6">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 200, damping: 15, delay: 0.2 }}
              className="mx-auto w-16 h-16 bg-emerald-100 dark:bg-emerald-900/30 rounded-full flex items-center justify-center mb-4"
            >
              <ShieldCheck className="w-8 h-8 text-emerald-600" />
            </motion.div>
            <h1 className="text-xl font-bold text-foreground">Verify Your Email</h1>
            <p className="text-sm text-muted-foreground">
              We sent a 6-digit code to{' '}
              <span className="font-medium text-foreground">{email}</span>
            </p>
          </CardHeader>
          <CardContent className="px-6 pb-2">
            <div className="space-y-6">
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

              {/* OTP Input Boxes */}
              <div className="flex justify-center gap-2 sm:gap-3">
                {Array.from({ length: OTP_LENGTH }).map((_, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                  >
                    <Input
                      ref={(el) => { inputRefs.current[index] = el; }}
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
                  </motion.div>
                ))}
              </div>

              <Button
                onClick={handleVerify}
                className="w-full h-11 text-sm font-semibold bg-emerald-600 hover:bg-emerald-700"
                disabled={isLoading || !isComplete}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Verifying...
                  </>
                ) : (
                  'Verify Code'
                )}
              </Button>
            </div>
          </CardContent>
          <CardFooter className="flex-col gap-4 pb-6 px-6">
            {/* Resend */}
            <div className="text-sm text-center">
              {cooldown > 0 ? (
                <span className="text-muted-foreground">
                  Resend code in{' '}
                  <span className="font-semibold text-foreground">{cooldown}s</span>
                </span>
              ) : (
                <button
                  onClick={handleResend}
                  disabled={isResending}
                  className="text-emerald-600 hover:text-emerald-700 font-semibold hover:underline disabled:opacity-50 inline-flex items-center gap-1.5"
                >
                  {isResending ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-3.5 h-3.5" />
                      Resend verification code
                    </>
                  )}
                </button>
              )}
            </div>

            {/* Back to login */}
            <button
              onClick={() => router.push(routes.login())}
              className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Back to login
            </button>
          </CardFooter>
        </Card>
      </motion.div>
    </div>
  );
}
