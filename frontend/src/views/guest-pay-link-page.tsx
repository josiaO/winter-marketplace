'use client';

import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { Lock, ShieldCheck, CheckCircle2, Loader2, Smartphone } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api-client';
import { formatTZS } from '@/lib/helpers';
import { toast } from 'sonner';
import { ApiClientError } from '@/types/api';
import { routes } from '@/lib/routes';
import Link from 'next/link';

type Tx = {
  amount?: string | number;
  currency?: string;
  status?: string;
  description?: string;
  seller_display?: string;
  metadata?: Record<string, unknown>;
};

export function GuestPayLinkPage({ token }: { token: string }) {
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [verified, setVerified] = useState(false);
  const [busy, setBusy] = useState(false);
  const [paidHold, setPaidHold] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await api.escrow.payLinkDetail(token);
      setDetail(d);
      const ov = Boolean(d?.otp_verified);
      setVerified(ov);
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.detail || e.message : 'Invalid or expired link');
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const txn = (detail?.transaction as Tx | undefined) || {};
  const amount = Number(txn.amount ?? 0);
  const currency = txn.currency || 'TZS';
  const title = String(detail?.title || txn.description || 'Payment');
  const meta = (txn.metadata || {}) as Record<string, unknown>;
  const imageUrl =
    (typeof meta.product_image === 'string' && meta.product_image) ||
    (typeof meta.image === 'string' && meta.image) ||
    '';

  const sendOtp = async () => {
    if (!phone.trim()) {
      toast.error('Enter your phone number');
      return;
    }
    setBusy(true);
    try {
      await api.escrow.payLinkRequestOtp(token, { phone: phone.trim() });
      setOtpSent(true);
      toast.success('Check your phone for the verification code.');
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.detail || e.message : 'Could not send code');
    } finally {
      setBusy(false);
    }
  };

  const verifyOtp = async () => {
    setBusy(true);
    try {
      await api.escrow.payLinkVerifyOtp(token, { phone: phone.trim(), otp: otp.trim() });
      setVerified(true);
      toast.success('Your number is verified.');
      await load();
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.detail || e.message : 'Invalid code');
    } finally {
      setBusy(false);
    }
  };

  const pay = async () => {
    const origin = typeof window !== 'undefined' ? window.location.origin : '';
    setBusy(true);
    try {
      const res = await api.escrow.payLinkPay(token, {
        buyer_phone: phone.trim(),
        buyer_name: '',
        redirect_url: origin ? `${origin}/pay/${token}` : '',
        cancel_url: origin ? `${origin}/pay/${token}` : '',
        payment_method: 'mobile_money',
        payment_channel: 'm_pesa',
      });
      if (res.payment_url) {
        window.location.assign(res.payment_url);
        return;
      }
      if (res.success) {
        setPaidHold(true);
        toast.success('Payment received and held safely.');
        await load();
      } else {
        toast.error(res.error || 'Payment could not start');
      }
    } catch (e) {
      toast.error(e instanceof ApiClientError ? e.detail || e.message : 'Payment failed');
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center px-4">
        <Loader2 className="w-10 h-10 animate-spin text-primary" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="max-w-lg mx-auto px-4 py-16 text-center">
        <p className="text-muted-foreground">This payment link is not available.</p>
        <Button asChild className="mt-6 rounded-xl">
          <Link href={routes.home()}>Home</Link>
        </Button>
      </div>
    );
  }

  const st = String(txn.status || '').toUpperCase();
  const isPaid = ['PAID', 'HOLD', 'RELEASED'].includes(st);

  return (
    <div className="max-w-lg mx-auto px-4 py-8 sm:py-12 space-y-6">
      <div className="text-center space-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-primary">SmartDalali</p>
        <h1 className="text-xl sm:text-2xl font-bold text-foreground">Secure Escrow Payment</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">What you are paying for</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {imageUrl ? (
            <div className="relative aspect-video rounded-lg overflow-hidden bg-muted">
              <Image src={imageUrl} alt="" fill className="object-cover" sizes="(max-width:512px) 100vw, 512px" />
            </div>
          ) : null}
          <p className="font-semibold text-foreground">{title}</p>
          <p className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">
            {formatTZS(amount)} {currency !== 'TZS' ? currency : ''}
          </p>
          <p className="text-sm text-muted-foreground">
            Seller: <span className="font-medium text-foreground">{txn.seller_display || 'Seller'}</span>
          </p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div className="rounded-xl border p-3 bg-muted/30">
          <Lock className="w-5 h-5 mx-auto mb-1 text-primary" />
          <p className="font-medium">Held until you confirm</p>
        </div>
        <div className="rounded-xl border p-3 bg-muted/30">
          <CheckCircle2 className="w-5 h-5 mx-auto mb-1 text-emerald-600" />
          <p className="font-medium">Released when satisfied</p>
        </div>
        <div className="rounded-xl border p-3 bg-muted/30">
          <ShieldCheck className="w-5 h-5 mx-auto mb-1 text-sky-600" />
          <p className="font-medium">Refund if not received</p>
        </div>
      </div>

      {!isPaid && !paidHold && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Verify your phone</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="phone">Phone number</Label>
              <Input
                id="phone"
                className="mt-1 rounded-lg"
                placeholder="e.g. 2557XXXXXXXX"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
              <p className="text-xs text-muted-foreground mt-1">We will send you a code to verify your number.</p>
            </div>
            {!otpSent ? (
              <Button className="w-full rounded-xl" onClick={() => void sendOtp()} disabled={busy}>
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Send code'}
              </Button>
            ) : (
              <>
                <div>
                  <Label htmlFor="otp">Enter code</Label>
                  <Input id="otp" className="mt-1 rounded-lg" value={otp} onChange={(e) => setOtp(e.target.value)} />
                </div>
                <Button className="w-full rounded-xl" onClick={() => void verifyOtp()} disabled={busy}>
                  Verify
                </Button>
              </>
            )}
            {verified && (
              <p className="text-xs text-emerald-700 dark:text-emerald-400">
                Your number is verified. Your identity is protected throughout this transaction.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {verified && !isPaid && !paidHold && (
        <Button className="w-full h-12 rounded-xl text-base font-semibold gap-2" onClick={() => void pay()} disabled={busy}>
          {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <Smartphone className="w-5 h-5" />}
          Pay {formatTZS(amount)} with M-Pesa
        </Button>
      )}

      {(isPaid || paidHold) && (
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          className="rounded-2xl border-2 border-emerald-200 dark:border-emerald-900 bg-emerald-50/80 dark:bg-emerald-950/30 p-6 text-center space-y-3"
        >
          <div className="flex justify-center">
            <div className="h-14 w-14 rounded-full bg-emerald-600 text-white flex items-center justify-center shadow-lg">
              <Lock className="w-7 h-7" />
            </div>
          </div>
          <p className="font-semibold text-foreground">Payment received and held safely.</p>
          <p className="text-sm text-muted-foreground">
            {txn.seller_display || 'The seller'} has been notified. When you receive your item, return here to confirm
            delivery and release payment.
          </p>
          <p className="text-xs text-muted-foreground">
            Save this page link — you can complete confirmation from any device.
          </p>
        </motion.div>
      )}

      <div className="rounded-xl border bg-muted/30 p-4 text-center text-sm space-y-2">
        <p className="font-medium text-foreground">Create an account to track this order</p>
        <div className="flex gap-2 justify-center flex-wrap">
          <Button asChild variant="default" className="rounded-xl">
            <Link href={routes.register()}>Create account</Link>
          </Button>
          <Button asChild variant="outline" className="rounded-xl">
            <Link href={routes.home()}>Maybe later</Link>
          </Button>
        </div>
      </div>
    </div>
  );
}
