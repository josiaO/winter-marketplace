'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { motion } from 'framer-motion';
import {
  ShoppingBag,
  Mail,
  Loader2,
  ArrowLeft,
  MailCheck,
  CheckCircle2,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useUIStore } from '@/store';
import { api } from '@/lib/api-client';
import { ApiClientError } from '@/lib/api-client';

interface ForgotPasswordFormValues {
  email: string;
}

export function ForgotPasswordPage() {
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [submittedEmail, setSubmittedEmail] = useState('');
  const { navigate } = useUIStore();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormValues>();

  const onSubmit = async (data: ForgotPasswordFormValues) => {
    setError('');
    setIsLoading(true);
    try {
      await api.auth.passwordReset({ email: data.email });
      setSubmittedEmail(data.email);
      setIsSuccess(true);
      toast.success('Password reset instructions have been sent to your email.');
    } catch (err: unknown) {
      let message = 'Failed to send reset instructions. Please try again.';
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
            onClick={() => navigate({ view: 'home' })}
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

        <Card className="border-0 shadow-xl shadow-black/5">
          {isSuccess ? (
            /* Success State */
            <>
              <CardHeader className="text-center pb-2 pt-8 px-6">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 200, damping: 15 }}
                  className="mx-auto w-16 h-16 bg-emerald-100 dark:bg-emerald-900/30 rounded-full flex items-center justify-center mb-4"
                >
                  <CheckCircle2 className="w-8 h-8 text-emerald-600" />
                </motion.div>
                <h1 className="text-xl font-bold text-foreground">Check Your Email</h1>
                <p className="text-sm text-muted-foreground mt-1">
                  We&apos;ve sent password reset instructions to
                </p>
                <p className="text-sm font-medium text-foreground">{submittedEmail}</p>
              </CardHeader>
              <CardContent className="px-6 pb-2">
                <div className="bg-emerald-50 dark:bg-emerald-950/20 rounded-lg p-4 text-center">
                  <div className="flex items-center justify-center gap-2 text-emerald-700 dark:text-emerald-400 text-sm">
                    <MailCheck className="w-4 h-4" />
                    <span>
                      If an account exists with this email, you&apos;ll receive a link to reset your
                      password shortly.
                    </span>
                  </div>
                </div>
              </CardContent>
              <CardFooter className="flex-col gap-4 pb-6 px-6">
                <Button
                  onClick={() => navigate({ view: 'login' })}
                  className="w-full h-11 text-sm font-semibold bg-emerald-600 hover:bg-emerald-700"
                >
                  Back to Login
                </Button>
                <button
                  onClick={() => {
                    setIsSuccess(false);
                    setSubmittedEmail('');
                  }}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  Try a different email address
                </button>
              </CardFooter>
            </>
          ) : (
            /* Form State */
            <>
              <CardHeader className="text-center pb-2 pt-6 px-6">
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 200, damping: 15, delay: 0.1 }}
                  className="mx-auto w-14 h-14 bg-amber-100 dark:bg-amber-900/30 rounded-full flex items-center justify-center mb-4"
                >
                  <Mail className="w-7 h-7 text-amber-600" />
                </motion.div>
                <h1 className="text-xl font-bold text-foreground">Forgot Password?</h1>
                <p className="text-sm text-muted-foreground">
                  Enter your email and we&apos;ll send you instructions to reset your password.
                </p>
              </CardHeader>
              <CardContent className="px-6 pb-2">
                <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
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

                  <div className="space-y-2">
                    <Label htmlFor="email" className="text-sm font-medium">
                      Email Address
                    </Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="email"
                        type="email"
                        placeholder="you@example.com"
                        autoComplete="email"
                        className="pl-10 h-11"
                        {...register('email', {
                          required: 'Email is required',
                          pattern: {
                            value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                            message: 'Please enter a valid email address',
                          },
                        })}
                      />
                    </div>
                    {errors.email && (
                      <p className="text-xs text-destructive">{errors.email.message}</p>
                    )}
                  </div>

                  <Button
                    type="submit"
                    className="w-full h-11 text-sm font-semibold bg-emerald-600 hover:bg-emerald-700"
                    disabled={isLoading}
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Sending...
                      </>
                    ) : (
                      'Send Reset Instructions'
                    )}
                  </Button>
                </form>
              </CardContent>
              <CardFooter className="flex-col gap-3 pb-6 px-6">
                <button
                  onClick={() => navigate({ view: 'login' })}
                  className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  Back to login
                </button>
              </CardFooter>
            </>
          )}
        </Card>
      </motion.div>
    </div>
  );
}
