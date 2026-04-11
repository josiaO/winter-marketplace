'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api-client';
import { Loader2, Landmark, Phone } from 'lucide-react';
import { InputOTP, InputOTPGroup, InputOTPSlot } from '@/components/ui/input-otp';

const PAYMENT_METHODS = [
  { id: 'mpesa', label: 'M-Pesa', color: 'text-green-600 bg-green-100', icon: Phone },
  { id: 'tigo_pesa', label: 'Tigo Pesa', color: 'text-blue-600 bg-blue-100', icon: Phone },
  { id: 'airtel_money', label: 'Airtel Money', color: 'text-red-600 bg-red-100', icon: Phone },
  { id: 'bank', label: 'Bank', color: 'text-gray-600 bg-gray-100', icon: Landmark },
];

export function SellerAddPayoutPage() {
  const router = useRouter();
  const [method, setMethod] = useState('mpesa');
  
  const [phone, setPhone] = useState('');
  const [bankCode, setBankCode] = useState('');
  const [accountName, setAccountName] = useState('');
  
  const [isLoading, setIsLoading] = useState(false);
  const [payoutId, setPayoutId] = useState<number | null>(null);
  
  const [code, setCode] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);

  const onSubmitAdd = async () => {
    if (!accountName.trim()) return toast.error('Account name is required.');
    if (method !== 'bank' && !phone.trim()) return toast.error('Phone number is required.');
    if (method === 'bank' && !phone.trim()) return toast.error('Account number is required.');
    
    setIsLoading(true);
    try {
      const res = await api.sellers.payoutAdd({
        account_type: method,
        account_number: phone.trim(),
        account_name: accountName.trim(),
        bank_code: bankCode.trim(),
      });
      setPayoutId(res.payout_account_id);
      toast.success(res.message || 'Check your SMS for the code');
    } catch (err: any) {
      toast.error(err.message || 'Failed to add payout account.');
    } finally {
      setIsLoading(false);
    }
  };

  const onVerify = async () => {
    if (!payoutId) return;
    if (code.length !== 6) return toast.error('Please enter the 6-digit code.');

    setIsVerifying(true);
    try {
      await api.sellers.payoutVerify({
        payout_account_id: payoutId,
        verification_code: code,
      });
      toast.success('Akaunti ya malipo imethibitishwa. Uko tayari kupokea malipo!');
      router.push(routes.sellerDashboard());
    } catch (err: any) {
      toast.error(err.message || 'Verification failed. Try again.');
    } finally {
      setIsVerifying(false);
    }
  };

  if (payoutId) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4">
        <div className="w-full max-w-sm text-center space-y-6">
          <div>
            <h2 className="text-2xl font-bold mb-2">Verify Payment Account</h2>
            <p className="text-sm text-muted-foreground">
              Tumetuma TZS 1 kwa {phone}. Angalia ujumbe wa malipo na uingize nambari ya tarakimu 6 uliyopata.
            </p>
          </div>
          
          <div className="flex justify-center py-4">
            <InputOTP maxLength={6} value={code} onChange={setCode}>
              <InputOTPGroup>
                <InputOTPSlot index={0} />
                <InputOTPSlot index={1} />
                <InputOTPSlot index={2} />
                <InputOTPSlot index={3} />
                <InputOTPSlot index={4} />
                <InputOTPSlot index={5} />
              </InputOTPGroup>
            </InputOTP>
          </div>

          <Button className="w-full" onClick={onVerify} disabled={isVerifying || code.length !== 6}>
            {isVerifying ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : 'Thibitisha'}
          </Button>

          <Button variant="link" onClick={onSubmitAdd} disabled={isLoading} className="text-muted-foreground text-sm">
            Hukupata? Tuma tena
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[80vh] px-4 py-12">
      <div className="max-w-xl mx-auto space-y-8">
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="text-center">
          <div className="text-4xl mb-4">🎉</div>
          <h1 className="text-3xl font-bold text-foreground">Hongera! Duka lako limeidhinishwa.</h1>
          <p className="text-muted-foreground mt-2">Hatua moja tu kubaki — tuambie tulipe wapi.</p>
        </motion.div>

        <div className="space-y-6 bg-card border rounded-xl p-6 shadow-sm">
          <div className="space-y-3">
            <Label className="text-base font-semibold">1. Payment Method</Label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {PAYMENT_METHODS.map((m) => (
                <button
                  key={m.id}
                  onClick={() => setMethod(m.id)}
                  className={`flex flex-col items-center justify-center p-3 rounded-lg border-2 transition-all ${
                    method === m.id ? 'border-primary ring-2 ring-primary/20' : 'border-muted hover:border-primary/50'
                  }`}
                >
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center mb-2 ${m.color}`}>
                    <m.icon className="w-4 h-4" />
                  </div>
                  <span className="text-xs font-semibold">{m.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            {method === 'bank' ? (
              <>
                <div className="space-y-2">
                  <Label>Bank Code / Name</Label>
                  <Input value={bankCode} onChange={e => setBankCode(e.target.value)} placeholder="e.g. CRDB" />
                </div>
                <div className="space-y-2">
                  <Label>Account Number</Label>
                  <Input value={phone} onChange={e => setPhone(e.target.value)} placeholder="Bank Account Number" />
                </div>
              </>
            ) : (
              <div className="space-y-2">
                <Label>Phone Number</Label>
                <Input value={phone} onChange={e => setPhone(e.target.value)} placeholder="e.g. 0712345678" />
              </div>
            )}
            
            <div className="space-y-2">
              <Label>Account Name</Label>
              <Input value={accountName} onChange={e => setAccountName(e.target.value)} placeholder="Name on the account" />
              <p className="text-xs text-muted-foreground">Must match your verified legal name.</p>
            </div>
          </div>

          <Button className="w-full h-12" onClick={onSubmitAdd} disabled={isLoading}>
            {isLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : 'Ongeza Akaunti →'}
          </Button>
        </div>
      </div>
    </div>
  );
}
