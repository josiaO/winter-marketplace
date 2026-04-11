'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useRef, ChangeEvent } from 'react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api-client';
import {
  IdCard,
  CreditCard,
  CarFront,
  FileCheck,
  Upload,
  Camera,
  CheckCircle2,
  Lock,
  ArrowLeft,
  Loader2,
  Image as ImageIcon
} from 'lucide-react';

const ID_TYPES = [
  { id: 'national_id', label: 'National ID', icon: IdCard },
  { id: 'passport', label: 'Passport', icon: FileCheck },
  { id: 'voters_card', label: 'Voter\'s Card', icon: CreditCard },
  { id: 'driving_license', label: 'Driving License', icon: CarFront },
];

export function SellerVerifyIdentityPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const [idType, setIdType] = useState('national_id');
  const [idNumber, setIdNumber] = useState('');
  const [idFront, setIdFront] = useState<File | null>(null);
  const [selfie, setSelfie] = useState<File | null>(null);

  const idInputRef = useRef<HTMLInputElement>(null);
  const selfieInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>, setter: (f: File | null) => void) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.size > 5 * 1024 * 1024) {
        toast.error('File maximum size is 5MB.');
        return;
      }
      setter(file);
    }
  };

  const onSubmit = async () => {
    if (!idNumber.trim()) return toast.error('Please enter your ID number.');
    if (!idFront) return toast.error('Please upload the front of your ID.');
    if (!selfie) return toast.error('Please upload a selfie holding your ID.');

    setIsLoading(true);
    try {
      await api.sellers.identitySubmit({
        id_type: idType,
        id_number: idNumber,
        id_front_image: idFront,
        selfie_with_id: selfie,
      });
      setIsSuccess(true);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Upload failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  if (isSuccess) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center px-4">
        <div className="text-center w-full max-w-sm space-y-6">
          <motion.div initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="flex justify-center">
            <div className="w-24 h-24 bg-green-100 rounded-full flex items-center justify-center mb-2">
              <CheckCircle2 className="w-12 h-12 text-green-600" />
            </div>
          </motion.div>
          <div>
            <h2 className="text-2xl font-bold text-foreground mb-2">Asante! Tunapitia nyaraka zako.</h2>
            <p className="text-muted-foreground text-sm">
              We are reviewing your documents. Tutakujulisha ndani ya masaa 24 kwa SMS na barua pepe.
            </p>
          </div>
          <Button className="w-full" onClick={() => router.push(routes.sellerDashboard())}>
            Rudi kwenye Dashibodi
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-2xl mx-auto space-y-8">
        <div>
          <div className="text-sm font-semibold text-primary mb-2 tracking-wider uppercase">Step 2 of 4: Verify Identity</div>
          <h1 className="text-3xl font-bold text-foreground">Confirm Your Identity</h1>
          <p className="text-muted-foreground mt-2">
            We need to confirm who you are so buyers can trust your store. 
            This takes about 5 minutes and we review within 24 hours.
          </p>
        </div>

        <div className="bg-muted/40 rounded-xl p-5 border">
          <h3 className="font-semibold mb-3">What you will need:</h3>
          <ul className="space-y-2">
            <li className="flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle2 className="w-4 h-4 text-green-500" />
              Your National ID, Passport, Voter's Card, or Driving License
            </li>
            <li className="flex items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle2 className="w-4 h-4 text-green-500" />
              A clear photo of yourself holding the ID
            </li>
          </ul>
        </div>

        <div className="space-y-6">
          <div className="space-y-3">
            <Label className="text-base font-semibold">1. Select ID Type</Label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {ID_TYPES.map((type) => (
                <button
                  key={type.id}
                  type="button"
                  onClick={() => setIdType(type.id)}
                  className={`flex flex-col items-center gap-2 p-3 rounded-lg border-2 transition-all ${
                    idType === type.id
                      ? 'border-primary bg-primary/5 text-primary'
                      : 'border-muted bg-card hover:border-primary/50 text-muted-foreground'
                  }`}
                >
                  <type.icon className="w-5 h-5" />
                  <span className="text-xs font-medium text-center">{type.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="idNumber" className="text-base font-semibold">2. ID Number</Label>
            <Input
              id="idNumber"
              value={idNumber}
              onChange={(e) => setIdNumber(e.target.value)}
              placeholder="Number shown on your ID"
              className="h-11"
            />
          </div>

          <div className="grid sm:grid-cols-2 gap-6">
            {/* Front of ID */}
            <div className="space-y-3">
              <Label className="text-base font-semibold block">3. Front of your ID</Label>
              <div 
                className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${idFront ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50'}`}
                onClick={() => idInputRef.current?.click()}
              >
                {idFront ? (
                  <div className="flex flex-col items-center text-primary">
                    <ImageIcon className="w-8 h-8 mb-2" />
                    <span className="text-sm font-medium">{idFront.name}</span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center text-muted-foreground">
                    <Upload className="w-8 h-8 mb-2 opacity-50" />
                    <span className="text-sm font-medium">Click to upload</span>
                    <span className="text-xs opacity-70 mt-1">Clear photo, all corners visible</span>
                  </div>
                )}
                <input 
                  type="file" 
                  accept="image/jpeg,image/png,application/pdf" 
                  className="hidden" 
                  ref={idInputRef}
                  onChange={(e) => handleFileChange(e, setIdFront)}
                />
              </div>
            </div>

            {/* Selfie */}
            <div className="space-y-3">
              <Label className="text-base font-semibold block">4. You holding your ID</Label>
              <div 
                className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${selfie ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50'}`}
                onClick={() => selfieInputRef.current?.click()}
              >
                {selfie ? (
                  <div className="flex flex-col items-center text-primary">
                    <ImageIcon className="w-8 h-8 mb-2" />
                    <span className="text-sm font-medium">{selfie.name}</span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center text-muted-foreground">
                    <Camera className="w-8 h-8 mb-2 opacity-50" />
                    <span className="text-sm font-medium">Click to upload</span>
                    <span className="text-xs opacity-70 mt-1">Hold ID next to face</span>
                  </div>
                )}
                <input 
                  type="file" 
                  accept="image/jpeg,image/png" 
                  className="hidden" 
                  ref={selfieInputRef}
                  onChange={(e) => handleFileChange(e, setSelfie)}
                />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/40 p-3 rounded-lg mt-4">
            <Lock className="w-4 h-4 shrink-0" />
            <p>Your documents are encrypted and only seen by our verification team. We never share them.</p>
          </div>

          <div className="pt-6 space-y-4">
            <Button className="w-full h-12 text-base" onClick={onSubmit} disabled={isLoading}>
              {isLoading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Uploading...</> : 'Tuma Nyaraka →'}
            </Button>
            <div className="text-center">
              <Button variant="link" className="text-muted-foreground" onClick={() => router.push(routes.sellerDashboard())}>
                <ArrowLeft className="w-4 h-4 mr-2" />
                Do this later
              </Button>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
