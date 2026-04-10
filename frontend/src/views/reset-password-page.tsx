'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod/v4';
import { zodResolver } from '@hookform/resolvers/zod';
import { motion } from 'framer-motion';
import {
  ShoppingBag,
  Lock,
  Eye,
  EyeOff,
  Loader2,
  ShieldCheck,
  ArrowLeft,
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

const resetPasswordSchema = z
  .object({
    new_password: z
      .string()
      .min(6, 'Password must be at least 6 characters')
      .max(100, 'Password is too long'),
    confirm_password: z.string(),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;

export function ResetPasswordPage() {
  const { currentView, navigate } = useUIStore();
  const uid = currentView.view === 'reset-password' ? currentView.uid : '';
  const token = currentView.view === 'reset-password' ? currentView.token : '';

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: {
      new_password: '',
      confirm_password: '',
    },
  });

  const onSubmit = async (data: ResetPasswordFormValues) => {
    if (!uid || !token) {
      setError('Invalid or missing reset credentials. Please request a new password reset.');
      return;
    }

    setError('');
    setIsLoading(true);
    try {
      await api.auth.passwordResetConfirm({
        uid,
        token,
        new_password: data.new_password,
        confirm_password: data.confirm_password,
      });
      setIsSuccess(true);
      toast.success('Password reset successfully! You can now log in with your new password.');
    } catch (err: unknown) {
      let message = 'Failed to reset password. The link may have expired.';
      if (err instanceof ApiClientError) {
        if (err.status === 400 || err.status === 401) {
          message =
            'This password reset link is invalid or has expired. Please request a new one.';
        } else {
          message = err.detail || err.message || message;
        }
      } else if (err instanceof Error) {
        message = err.message;
      }
      setError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  // Guard: if no uid/token, show error
  if (!uid || !token) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md"
        >
          <div className="flex flex-col items-center mb-8">
            <div className="w-12 h-12 bg-emerald-600 rounded-2xl flex items-center justify-center">
              <ShoppingBag className="w-7 h-7 text-white" />
            </div>
          </div>
          <Card className="border-0 shadow-xl shadow-black/5">
            <CardContent className="p-6 text-center space-y-4">
              <div className="mx-auto w-14 h-14 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
                <ShieldCheck className="w-7 h-7 text-red-600" />
              </div>
              <p className="text-muted-foreground">
                Invalid or missing reset credentials. Please request a new password reset link.
              </p>
              <Button
                onClick={() => navigate({ view: 'forgot-password' })}
                className="bg-emerald-600 hover:bg-emerald-700 border-0"
              >
                Request Reset Link
              </Button>
            </CardContent>
          </Card>
        </motion.div>
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
                <h1 className="text-xl font-bold text-foreground">Password Reset!</h1>
                <p className="text-sm text-muted-foreground">
                  Your password has been changed successfully.
                </p>
              </CardHeader>
              <CardContent className="px-6 pb-2">
                <div className="bg-emerald-50 dark:bg-emerald-950/20 rounded-lg p-4 text-center text-sm text-emerald-700 dark:text-emerald-400">
                  You can now sign in with your new password.
                </div>
              </CardContent>
              <CardFooter className="pb-6 px-6">
                <Button
                  onClick={() => navigate({ view: 'login' })}
                  className="w-full h-11 text-sm font-semibold bg-emerald-600 hover:bg-emerald-700"
                >
                  Sign In
                </Button>
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
                  className="mx-auto w-14 h-14 bg-emerald-100 dark:bg-emerald-900/30 rounded-full flex items-center justify-center mb-4"
                >
                  <Lock className="w-7 h-7 text-emerald-600" />
                </motion.div>
                <h1 className="text-xl font-bold text-foreground">Set New Password</h1>
                <p className="text-sm text-muted-foreground">
                  Choose a strong password for your account.
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
                    <Label htmlFor="new_password" className="text-sm font-medium">
                      New Password
                    </Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="new_password"
                        type={showPassword ? 'text' : 'password'}
                        placeholder="Min. 6 characters"
                        autoComplete="new-password"
                        className="pl-10 pr-10 h-11"
                        {...register('new_password')}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {showPassword ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                    {errors.new_password && (
                      <p className="text-xs text-destructive">{errors.new_password.message}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="confirm_password" className="text-sm font-medium">
                      Confirm New Password
                    </Label>
                    <div className="relative">
                      <ShieldCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="confirm_password"
                        type={showConfirm ? 'text' : 'password'}
                        placeholder="Re-enter your password"
                        autoComplete="new-password"
                        className="pl-10 pr-10 h-11"
                        {...register('confirm_password')}
                      />
                      <button
                        type="button"
                        onClick={() => setShowConfirm(!showConfirm)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {showConfirm ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                    {errors.confirm_password && (
                      <p className="text-xs text-destructive">
                        {errors.confirm_password.message}
                      </p>
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
                        Resetting...
                      </>
                    ) : (
                      'Reset Password'
                    )}
                  </Button>
                </form>
              </CardContent>
              <CardFooter className="pb-6 px-6">
                <button
                  onClick={() => navigate({ view: 'login' })}
                  className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors mx-auto"
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
