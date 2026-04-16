'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ShieldCheck, 
  Lock, 
  CheckCircle2, 
  Package, 
  ArrowRight, 
  CreditCard,
  Mail,
  Smartphone,
  AlertCircle,
  Loader2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Card, CardContent } from '@/components/ui/card';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api-client';
import { formatTZS } from '@/lib/helpers';
import { toast } from 'sonner';
import { ApiClientError } from '@/types/api';
import { useRouter } from 'next/navigation';

export function GuestPayLinkPage({ token }: { token: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [linkData, setLinkData] = useState<any>(null);
  const [step, setStep] = useState<'info' | 'otp' | 'verified'>('info');
  
  const [channel, setChannel] = useState<'sms' | 'email'>('sms');
  const [destination, setDestination] = useState('');
  const [otp, setOtp] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadDetail = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await api.escrow.payLinkDetail(token);
      setLinkData(res);
      if (res.otp_verified) setStep('verified');
    } catch (err: any) {
      toast.error(err instanceof ApiClientError ? err.detail || err.message : "Invalid or expired payment link");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const handleRequestOtp = async () => {
    if (!destination) {
      toast.error(`Please enter your ${channel === 'sms' ? 'phone number' : 'email'}`);
      return;
    }
    setSubmitting(true);
    try {
      // Note: Backend currently seems to prioritize phone in payLinkRequestOtp
      await api.escrow.payLinkRequestOtp(token, { phone: destination });
      toast.success(`Verification code sent to your ${channel}`);
      setStep('otp');
    } catch (err: any) {
      toast.error(err instanceof ApiClientError ? err.detail || err.message : "Failed to send code");
    } finally {
      setSubmitting(false);
    }
  };

  const handleVerifyOtp = async () => {
    if (otp.length < 4) return;
    setSubmitting(true);
    try {
      await api.escrow.payLinkVerifyOtp(token, { phone: destination, otp });
      toast.success("Identity verified successfully");
      setStep('verified');
    } catch (err: any) {
      toast.error("Invalid or expired code. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const handlePay = async () => {
    setSubmitting(true);
    try {
      const origin = typeof window !== 'undefined' ? window.location.origin : '';
      const res = await api.escrow.payLinkPay(token, {
        buyer_phone: destination,
        redirect_url: origin ? `${origin}/pay/${token}` : '',
        cancel_url: origin ? `${origin}/pay/${token}` : '',
        payment_method: 'mobile_money',
        payment_channel: 'm_pesa', // Defaulting to M-Pesa
      });
      if (res.payment_url) {
        window.location.href = res.payment_url;
      } else if (res.success) {
        toast.success("Payment initiated successfully");
        void loadDetail();
      }
    } catch (err: any) {
      toast.error(err instanceof ApiClientError ? err.detail || err.message : "Payment initiation failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-600" />
      </div>
    );
  }

  if (!linkData) return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center p-6 text-center space-y-4">
      <AlertCircle className="w-16 h-16 text-destructive opacity-20" />
      <h1 className="text-xl font-bold">Link Not Found</h1>
      <p className="text-muted-foreground text-sm max-w-xs">This payment link may have expired or was already used.</p>
      <Button onClick={() => router.push('/')} variant="outline" className="rounded-xl px-8">Go Home</Button>
    </div>
  );

  const txn = linkData.transaction || {};
  const isPaid = ['PAID', 'HOLD', 'RELEASED'].includes(String(txn.status || '').toUpperCase());

  return (
    <div className="py-8 px-4 sm:px-6">
      <div className="max-w-md mx-auto space-y-6">
        {/* Branding & Trust */}
        <div className="flex flex-col items-center text-center space-y-2">
          <div className="w-14 h-14 bg-emerald-100 dark:bg-emerald-950/40 rounded-[22px] flex items-center justify-center text-emerald-600 mb-2 shadow-sm border border-emerald-200/50">
            <ShieldCheck className="w-8 h-8" />
          </div>
          <h1 className="text-xl font-bold text-foreground">SmartDalali Secure Checkout</h1>
          <p className="text-xs text-muted-foreground max-w-[280px]">
            Funds are managed by our escrow engine until delivery is successful.
          </p>
        </div>

        <Card className="overflow-hidden border-none shadow-2xl rounded-[32px] bg-card/80 backdrop-blur-md">
          <CardContent className="p-0">
            {/* Order Summary Header */}
            <div className="bg-emerald-600 p-8 text-white space-y-1 relative overflow-hidden">
               {/* Pattern Overlay */}
              <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2 blur-2xl" />
              
              <p className="text-[10px] uppercase font-black tracking-[0.2em] opacity-80">Payment Request</p>
              <h2 className="text-4xl font-black tabular-nums">{formatTZS(txn.amount)}</h2>
              <div className="flex items-center gap-2 pt-2">
                <Badge className="bg-emerald-500/50 hover:bg-emerald-500/60 border-none text-white backdrop-blur-md px-2 py-0.5 text-[10px] font-bold">
                  <Lock className="w-3 h-3 mr-1" /> SECURE ESCROW
                </Badge>
              </div>
            </div>

            <div className="p-8 space-y-6">
              {/* Item Details */}
              <div className="flex gap-4 items-start">
                <div className="w-12 h-12 bg-muted/50 rounded-2xl flex items-center justify-center text-muted-foreground border border-black/5 dark:border-white/5">
                  <Package className="w-6 h-6" />
                </div>
                <div className="flex-1">
                  <h3 className="font-bold text-foreground text-sm line-clamp-1">{linkData.title || "Secure Purchase"}</h3>
                  <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                    {linkData.description || txn.description || "You are making a secure payment via SmartDalali Escrow Protection."}
                  </p>
                </div>
              </div>

              <Separator className="opacity-50" />

              {/* Steps Flow */}
              <AnimatePresence mode="wait">
                {isPaid ? (
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
                      The seller has been notified. When you receive your item, return here to confirm
                      delivery and release payment.
                    </p>
                  </motion.div>
                ) : (
                  <>
                    {step === 'info' && (
                      <motion.div
                        key="info"
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        className="space-y-5"
                      >
                        <div className="space-y-4">
                          <Label className="text-xs font-black uppercase tracking-widest text-muted-foreground">Verify your identity to proceed</Label>
                          <RadioGroup 
                            value={channel} 
                            onValueChange={(v: any) => setChannel(v)}
                            className="grid grid-cols-2 gap-3"
                          >
                            <Label
                              className={`flex items-center gap-2 p-4 rounded-2xl border-2 transition-all cursor-pointer ${
                                channel === 'sms' ? 'border-emerald-600 bg-emerald-500/5' : 'border-muted hover:border-muted-foreground/30'
                              }`}
                            >
                              <RadioGroupItem value="sms" className="sr-only" />
                              <Smartphone className={`w-4 h-4 ${channel === 'sms' ? 'text-emerald-600' : 'text-muted-foreground'}`} />
                              <span className="text-xs font-bold">Phone</span>
                            </Label>
                            <Label
                              className={`flex items-center gap-2 p-4 rounded-2xl border-2 transition-all cursor-pointer ${
                                channel === 'email' ? 'border-emerald-600 bg-emerald-500/5' : 'border-muted hover:border-muted-foreground/30'
                              }`}
                            >
                              <RadioGroupItem value="email" className="sr-only" />
                              <Mail className={`w-4 h-4 ${channel === 'email' ? 'text-emerald-600' : 'text-muted-foreground'}`} />
                              <span className="text-xs font-bold">Email</span>
                            </Label>
                          </RadioGroup>

                          <div className="relative group">
                            <Input 
                              placeholder={channel === 'sms' ? "Phone: 255XXXXXXXXX" : "Email: name@example.com"}
                              type={channel === 'email' ? "email" : "tel"}
                              value={destination}
                              onChange={(e) => setDestination(e.target.value)}
                              className="h-14 rounded-2xl bg-muted/30 border-none shadow-none focus-visible:ring-emerald-600 px-4 text-sm font-medium"
                            />
                          </div>
                        </div>
                        
                        <Button 
                          className="w-full h-14 rounded-2xl text-base font-black bg-emerald-600 hover:bg-emerald-700 shadow-xl shadow-emerald-600/20 active:scale-[0.98] transition-all"
                          onClick={handleRequestOtp}
                          disabled={submitting || !destination}
                        >
                          {submitting ? <Loader2 className="w-6 h-6 animate-spin" /> : "Verify Identity"}
                        </Button>
                      </motion.div>
                    )}

                    {step === 'otp' && (
                      <motion.div
                        key="otp"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        className="space-y-6"
                      >
                        <div className="space-y-4 text-center">
                          <div className="inline-flex items-center justify-center w-12 h-12 bg-emerald-100 rounded-full text-emerald-600 mb-2">
                             <Mail className="w-6 h-6" />
                          </div>
                          <p className="text-sm text-muted-foreground">
                            Enter the 6-digit code sent to <br />
                            <span className="font-bold text-foreground">{destination}</span>
                          </p>
                          <Input 
                            placeholder="000000"
                            className="h-16 text-center text-3xl font-black tracking-[0.4em] rounded-2xl bg-muted/30 border-none px-4"
                            maxLength={6}
                            value={otp}
                            onChange={(e) => setOtp(e.target.value)}
                            autoFocus
                          />
                        </div>
                        
                        <Button 
                          className="w-full h-14 rounded-2xl text-base font-black bg-emerald-600 hover:bg-emerald-700 shadow-xl shadow-emerald-600/20"
                          onClick={handleVerifyOtp}
                          disabled={submitting || otp.length < 4}
                        >
                          {submitting ? <Loader2 className="w-6 h-6 animate-spin" /> : "Confirm & Unlock Payment"}
                        </Button>
                        <Button 
                          variant="ghost" 
                          className="w-full text-xs text-muted-foreground hover:bg-transparent"
                          onClick={() => setStep('info')}
                        >
                          Use a different {channel === 'sms' ? 'phone' : 'email'}
                        </Button>
                      </motion.div>
                    )}

                    {step === 'verified' && (
                      <motion.div
                        key="verified"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="space-y-6"
                      >
                        <div className="bg-emerald-50 dark:bg-emerald-600/10 p-5 rounded-3xl flex items-center gap-4 border border-emerald-100 dark:border-emerald-600/20">
                          <div className="w-12 h-12 bg-emerald-600 rounded-full flex items-center justify-center text-white shadow-lg shadow-emerald-600/20">
                            <CheckCircle2 className="w-7 h-7" />
                          </div>
                          <div>
                            <p className="text-sm font-black text-emerald-900 dark:text-emerald-400">Buyer Verified</p>
                            <p className="text-[11px] text-emerald-700 dark:text-emerald-500 font-medium">Identity confirmed. Escrow protection is ready.</p>
                          </div>
                        </div>

                        <div className="space-y-3">
                          <div className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-muted-foreground">
                            <CreditCard className="w-3 h-3" />
                            <span>Payment Method</span>
                          </div>
                          <div className="p-5 border-2 border-emerald-600 bg-emerald-600/5 rounded-3xl flex items-center justify-between shadow-inner">
                            <div className="flex items-center gap-4">
                              <div className="w-12 h-12 bg-white dark:bg-black rounded-xl border flex items-center justify-center font-black italic text-emerald-600 text-xl shadow-sm">S</div>
                              <div className="space-y-0.5">
                                <span className="font-black text-sm">Selcom Global</span>
                                <p className="text-[10px] text-muted-foreground">Mobile Money, Cards, Bank Transfer</p>
                              </div>
                            </div>
                            <CheckCircle2 className="w-6 h-6 text-emerald-600" />
                          </div>
                        </div>

                        <div className="pt-2">
                          <Button 
                            className="w-full h-16 rounded-3xl text-lg font-black bg-emerald-600 hover:bg-emerald-700 shadow-2xl shadow-emerald-600/40 active:scale-[0.98] transition-all group"
                            onClick={handlePay}
                            disabled={submitting}
                          >
                            {submitting ? <Loader2 className="w-7 h-7 animate-spin" /> : (
                              <>
                                Secure Payment Now <ArrowRight className="ml-2 w-6 h-6 group-hover:translate-x-1 transition-transform" />
                              </>
                            )}
                          </Button>
                          <p className="text-center text-[10px] text-muted-foreground mt-4 px-6 leading-relaxed">
                            By clicking pay, you agree to SmartDalali&apos;s Escrow Terms. Funds are held until you confirm receipt.
                          </p>
                        </div>
                      </motion.div>
                    )}
                  </>
                )}
              </AnimatePresence>
            </div>
          </CardContent>
        </Card>

        {/* Footer Trust Indicators */}
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col items-center text-center space-y-2 p-5 bg-card/40 rounded-3xl border border-black/5 dark:border-white/5 backdrop-blur-sm">
            <ShieldCheck className="w-6 h-6 text-emerald-600" />
            <div className="space-y-0.5">
              <p className="text-[11px] font-black uppercase tracking-tighter">Buyer Rights</p>
              <p className="text-[10px] text-muted-foreground leading-tight px-1">Full refund if item not as described</p>
            </div>
          </div>
          <div className="flex flex-col items-center text-center space-y-2 p-5 bg-card/40 rounded-3xl border border-black/5 dark:border-white/5 backdrop-blur-sm">
            <Lock className="w-6 h-6 text-emerald-600" />
            <div className="space-y-0.5">
              <p className="text-[11px] font-black uppercase tracking-tighter">Secure Holding</p>
              <p className="text-[10px] text-muted-foreground leading-tight px-1">Funds locked in escrow during transit</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
