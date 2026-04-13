'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback, useRef } from 'react';
import { motion } from 'framer-motion';
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  ShieldOff,
  Upload,
  X,
  Loader2,
  ArrowLeft,
  Info,
  BadgeCheck,
  FileText,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import type { VerificationStatus } from '@/types/api';

// ─── Types ────────────────────────────────────────────────────────────────────

type IdentityStatus = 'not_started' | 'under_review' | 'verified' | 'rejected' | string;

// ─── Helpers ──────────────────────────────────────────────────────────────────

function getStatusConfig(status: VerificationStatus) {
  switch (status) {
    case 'verified':
      return {
        icon: ShieldCheck,
        color: 'text-green-600 dark:text-green-400',
        bg: 'bg-green-100 dark:bg-green-900/30',
        badgeColor: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
        label: 'Verified',
        progress: 100,
      };
    case 'pending':
      return {
        icon: ShieldAlert,
        color: 'text-amber-600 dark:text-amber-400',
        bg: 'bg-amber-100 dark:bg-amber-900/30',
        badgeColor: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
        label: 'Pending Review',
        progress: 50,
      };
    case 'rejected':
      return {
        icon: ShieldAlert,
        color: 'text-red-600 dark:text-red-400',
        bg: 'bg-red-100 dark:bg-red-900/30',
        badgeColor: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
        label: 'Rejected',
        progress: 25,
      };
    case 'unverified':
    default:
      return {
        icon: ShieldOff,
        color: 'text-gray-600 dark:text-gray-400',
        bg: 'bg-gray-100 dark:bg-gray-800',
        badgeColor: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
        label: 'Not Verified',
        progress: 0,
      };
  }
}

function getStatusExplanation(status: VerificationStatus): string {
  switch (status) {
    case 'verified':
      return 'Your seller account has been fully verified. You have access to all seller features and your listings will display a verified badge.';
    case 'pending':
      return 'Your verification documents are being reviewed. This typically takes 1-3 business days. You can still sell, but your verified badge will appear once approved.';
    case 'rejected':
      return 'Your verification was rejected. Please review the feedback and resubmit the required documents. Contact support if you need assistance.';
    case 'unverified':
    default:
      return 'Complete the verification process to unlock all seller features and gain buyer trust with a verified badge on your listings.';
  }
}

// ─── Component ─────────────────────────────────────────────────────────────────

export function SellerVerificationPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [isLoading, setIsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [idType, setIdType] = useState<
    'national_id' | 'passport' | 'voters_card' | 'driving_license'
  >('national_id');
  const [idNumber, setIdNumber] = useState('');
  const [idFront, setIdFront] = useState<File | null>(null);
  const [selfieWithId, setSelfieWithId] = useState<File | null>(null);

  const [identityStatus, setIdentityStatus] = useState<IdentityStatus>('not_started');
  const [rejectionReason, setRejectionReason] = useState<string | null>(null);
  const [onboarding, setOnboarding] = useState<any>(null);

  // Business verification state
  const [businessName, setBusinessName] = useState('');
  const [licenseNumber, setLicenseNumber] = useState('');
  const [tinNumber, setTinNumber] = useState('');
  const [businessCert, setBusinessCert] = useState<File | null>(null);
  const [businessSubmitting, setBusinessSubmitting] = useState(false);

  const sellerProfile = user?.seller_profile;
  const verificationStatus: VerificationStatus = sellerProfile?.verification_status || 'unverified';
  const statusConfig = getStatusConfig(verificationStatus);
  const StatusIcon = statusConfig.icon;

  // ─── Auth guard ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) {
      router.push(routes.login());
      return;
    }
    if (!user?.is_seller) {
      toast.error('You must be a seller to access verification.');
      router.push(routes.sellerRegister());
    }
  }, [isAuthenticated, user, router]);

  const idFrontInputRef = useRef<HTMLInputElement>(null);
  const selfieInputRef = useRef<HTMLInputElement>(null);
  const businessCertInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const [st, prog] = await Promise.all([
        api.sellers.identityVerificationStatus(),
        api.sellers.onboardingProgress(),
      ]);
      setIdentityStatus((st as any)?.status || 'not_started');
      setRejectionReason((st as any)?.rejection_reason || null);
      setOnboarding(prog as any);
    } catch {
      // Non-critical: keep page usable even if status endpoints fail.
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated || !user?.is_seller) return;
    refresh();
  }, [isAuthenticated, user, refresh]);

  if (!isAuthenticated || !user) return null;

  const completion = onboarding?.completion_percentage ?? 0;

  return (
    <div className="space-y-6">
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
              onClick={() => router.push(routes.sellerDashboard())}
              className="shrink-0"
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
                Seller Verification
              </h1>
              <p className="text-muted-foreground mt-1">
                Verify your account to build trust with buyers
              </p>
            </div>
          </div>
          <Badge className={`${statusConfig.badgeColor} text-sm px-3 py-1`}>
            <StatusIcon className="w-4 h-4 mr-1.5" />
            {statusConfig.label}
          </Badge>
        </motion.div>

        {/* Onboarding progress */}
        <Card className="border-0 shadow-md shadow-black/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg">Onboarding Progress</CardTitle>
            <CardDescription>Complete identity verification to unlock payouts.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : (
              <>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Completion</span>
                  <span className="font-medium">{completion}%</span>
                </div>
                <Progress value={completion} className="h-2" />
              </>
            )}
          </CardContent>
        </Card>

        {/* Status Overview Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className={`w-14 h-14 rounded-2xl flex items-center justify-center shrink-0 ${statusConfig.bg}`}>
                  <StatusIcon className={`w-7 h-7 ${statusConfig.color}`} />
                </div>
                <div className="flex-1 space-y-3">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">
                      Verification Status: {statusConfig.label}
                    </h2>
                    <p className="text-sm text-muted-foreground mt-1">
                      {getStatusExplanation(verificationStatus)}
                    </p>
                  </div>
                  {identityStatus === 'rejected' && rejectionReason && (
                    <Alert variant="destructive" className="border-0">
                      <AlertDescription className="text-sm">
                        <span className="font-medium">Rejection reason:</span> {rejectionReason}
                      </AlertDescription>
                    </Alert>
                  )}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">
                        Identity status: {String(identityStatus)}
                      </span>
                      <span className={`font-medium ${statusConfig.color}`}>
                        {statusConfig.progress}%
                      </span>
                    </div>
                    <Progress value={statusConfig.progress} className="h-2" />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Benefits Info */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Alert className="border-primary/20 bg-primary/5 dark:bg-primary/5">
            <Info className="h-4 w-4 text-primary" />
            <AlertDescription className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">Why verify? </span>
              Verified sellers gain buyer trust, get a verified badge on their listings, and may receive priority support and higher visibility in search results.
            </AlertDescription>
          </Alert>
        </motion.div>

        {/* Identity verification submission */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Shield className="w-5 h-5 text-primary" />
                Submit identity for review
              </CardTitle>
              <CardDescription>
                Upload your ID front photo and a selfie holding your ID. Accepted: images up to 10MB.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-sm font-medium text-foreground">ID Type</label>
                  <select
                    className="w-full h-10 rounded-md border bg-background px-3 text-sm"
                    value={idType}
                    onChange={(e) => setIdType(e.target.value as any)}
                  >
                    <option value="national_id">National ID</option>
                    <option value="passport">Passport</option>
                    <option value="voters_card">Voter&apos;s card</option>
                    <option value="driving_license">Driving license</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium text-foreground">ID Number</label>
                  <input
                    className="w-full h-10 rounded-md border bg-background px-3 text-sm"
                    value={idNumber}
                    onChange={(e) => setIdNumber(e.target.value)}
                    placeholder="Enter your ID number"
                  />
                </div>
              </div>

              <Separator />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 rounded-xl border bg-card/50 space-y-2">
                  <p className="font-medium text-foreground text-sm">ID front image</p>
                  <input
                    ref={idFrontInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0] || null;
                      setIdFront(f);
                      e.target.value = '';
                    }}
                  />
                  <Button variant="outline" className="w-full gap-2" onClick={() => idFrontInputRef.current?.click()}>
                    <Upload className="w-4 h-4" />
                    {idFront ? 'Replace' : 'Upload'}
                  </Button>
                  {idFront && (
                    <Button variant="ghost" className="w-full gap-2" onClick={() => setIdFront(null)}>
                      <X className="w-4 h-4" />
                      Remove
                    </Button>
                  )}
                </div>
                <div className="p-4 rounded-xl border bg-card/50 space-y-2">
                  <p className="font-medium text-foreground text-sm">Selfie with ID</p>
                  <input
                    ref={selfieInputRef}
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0] || null;
                      setSelfieWithId(f);
                      e.target.value = '';
                    }}
                  />
                  <Button variant="outline" className="w-full gap-2" onClick={() => selfieInputRef.current?.click()}>
                    <Upload className="w-4 h-4" />
                    {selfieWithId ? 'Replace' : 'Upload'}
                  </Button>
                  {selfieWithId && (
                    <Button variant="ghost" className="w-full gap-2" onClick={() => setSelfieWithId(null)}>
                      <X className="w-4 h-4" />
                      Remove
                    </Button>
                  )}
                </div>
              </div>

              <Button
                className="w-full gap-2"
                disabled={submitting}
                onClick={async () => {
                  if (!idFront || !selfieWithId) {
                    toast.error('Please upload both images.');
                    return;
                  }
                  if (!idNumber.trim()) {
                    toast.error('Please enter your ID number.');
                    return;
                  }
                  setSubmitting(true);
                  try {
                    await api.sellers.submitIdentityVerification({
                      id_type: idType,
                      id_number: idNumber.trim(),
                      id_front_image: idFront,
                      selfie_with_id: selfieWithId,
                    });
                    toast.success('Identity submitted. We will review it shortly.');
                    setIdFront(null);
                    setSelfieWithId(null);
                    await refresh();
                  } catch (err) {
                    const message =
                      err instanceof Error ? err.message : 'Failed to submit identity verification.';
                    toast.error(message);
                  } finally {
                    setSubmitting(false);
                  }
                }}
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Shield className="w-4 h-4" />}
                Submit
              </Button>
            </CardContent>
          </Card>
        </motion.div>

        {/* Business verification submission */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <BadgeCheck className="w-5 h-5 text-primary" />
                Business Verification (Upgrade)
              </CardTitle>
              <CardDescription>
                Upgrade to a business account to increase your limits and gain maximum trust.
                Requires 500k TZS total sales or 20 completed orders.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-sm font-medium text-foreground">Business Name</label>
                  <input
                    className="w-full h-10 rounded-md border bg-background px-3 text-sm"
                    value={businessName}
                    onChange={(e) => setBusinessName(e.target.value)}
                    placeholder="Enter registered business name"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium text-foreground">TIN Number</label>
                  <input
                    className="w-full h-10 rounded-md border bg-background px-3 text-sm"
                    value={tinNumber}
                    onChange={(e) => setTinNumber(e.target.value)}
                    placeholder="Enter TIN number"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-sm font-medium text-foreground">License Number</label>
                  <input
                    className="w-full h-10 rounded-md border bg-background px-3 text-sm"
                    value={licenseNumber}
                    onChange={(e) => setLicenseNumber(e.target.value)}
                    placeholder="Enter business license number"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium text-foreground">Business Certificate (PDF/Image)</label>
                  <input
                    ref={businessCertInputRef}
                    type="file"
                    accept="image/*,.pdf"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0] || null;
                      setBusinessCert(f);
                      e.target.value = '';
                    }}
                  />
                  <Button variant="outline" className="w-full gap-2 h-10" onClick={() => businessCertInputRef.current?.click()}>
                    <Upload className="w-4 h-4" />
                    {businessCert ? 'Replace Certificate' : 'Upload Certificate'}
                  </Button>
                </div>
              </div>

              {businessCert && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground p-2 bg-muted/30 rounded-md">
                  <FileText className="w-3 h-3" />
                  <span className="truncate flex-1">{businessCert.name}</span>
                  <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setBusinessCert(null)}>
                    <X className="w-3 h-3" />
                  </Button>
                </div>
              )}

              <Button
                className="w-full gap-2"
                disabled={businessSubmitting}
                variant="secondary"
                onClick={async () => {
                  if (!businessName || !tinNumber) {
                    toast.error('Business name and TIN number are required.');
                    return;
                  }
                  setBusinessSubmitting(true);
                  try {
                    await api.sellers.submitBusinessVerification({
                      business_name: businessName,
                      tin_number: tinNumber,
                      business_registration_no: licenseNumber,
                      business_certificate: businessCert || undefined
                    });
                    toast.success('Business verification submitted. We will review it shortly.');
                    setBusinessName('');
                    setTinNumber('');
                    setLicenseNumber('');
                    setBusinessCert(null);
                    await refresh();
                  } catch (err) {
                    const message =
                      err instanceof Error ? err.message : 'Failed to submit business verification.';
                    toast.error(message);
                  } finally {
                    setBusinessSubmitting(false);
                  }
                }}
              >
                {businessSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                Submit Upgrade Request
              </Button>
            </CardContent>
          </Card>
        </motion.div>

        {/* Additional Info */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardContent className="p-5">
              <h3 className="font-semibold text-foreground mb-3">Verification Guidelines</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2">
                  <span className="w-4 h-4 text-primary shrink-0 mt-0.5">•</span>
                  <span>Documents must be clear, legible, and show your full name</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-4 h-4 text-primary shrink-0 mt-0.5">•</span>
                  <span>Accepted formats: PNG, JPG, WEBP, PDF (max 10MB)</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-4 h-4 text-primary shrink-0 mt-0.5">•</span>
                  <span>Verification is typically processed within 1-3 business days</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-4 h-4 text-primary shrink-0 mt-0.5">•</span>
                  <span>If rejected, you can resubmit corrected documents</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="w-4 h-4 text-primary shrink-0 mt-0.5">•</span>
                  <span>All documents are kept confidential and encrypted</span>
                </li>
              </ul>
            </CardContent>
          </Card>
        </motion.div>
    </div>
  );
}
