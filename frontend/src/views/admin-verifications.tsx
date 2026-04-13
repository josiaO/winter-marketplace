'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield, CheckCircle2, XCircle, Clock, ArrowUpRight, Loader2,
  ChevronLeft, ChevronRight, User, Image as ImageIcon, Briefcase, Eye
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { getRelativeTime } from '@/lib/helpers';

const PAGE_SIZE = 20;

export function AdminVerificationsPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();

  const [verifications, setVerifications] = useState<any[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('pending'); // pending, approved, rejected
  const [page, setPage] = useState(1);

  const [selectedDetail, setSelectedDetail] = useState<any | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<any | null>(null);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const fetchVerifications = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await api.sellers.adminVerifications({
        status: activeTab,
        page: page,
        page_size: PAGE_SIZE
      });
      setVerifications(res.results || []);
      setTotalCount(res.count || 0);
    } catch {
      toast.error('Failed to load verifications.');
    } finally {
      setIsLoading(false);
    }
  }, [activeTab, page]);

  useEffect(() => {
    if (isAuthenticated && user?.role === 'admin') {
      fetchVerifications();
    }
  }, [isAuthenticated, user, fetchVerifications]);

  const handleReview = async (verification: any) => {
    setSelectedDoc(verification);
    setIsDetailLoading(true);
    try {
      const detail = await api.sellers.adminSellerDetail(verification.id);
      setSelectedDetail(detail);
    } catch {
      toast.error('Failed to load seller details.');
    } finally {
      setIsDetailLoading(false);
    }
  };

  const onApprove = async () => {
    if (!selectedDoc) return;
    setIsActionLoading(true);
    try {
      await api.sellers.adminVerifyApprove(selectedDoc.id);
      toast.success('Seller approved successfully.');
      setSelectedDoc(null);
      setSelectedDetail(null);
      fetchVerifications();
    } catch (err: any) {
      toast.error(err.message || 'Failed to approve seller.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const onReject = async () => {
    if (!selectedDoc) return;
    if (!rejectReason.trim()) return toast.error('You must provide a reason for rejection.');
    setIsActionLoading(true);
    try {
      await api.sellers.adminVerifyReject(selectedDoc.id, { reason: rejectReason });
      toast.success('Seller rejected.');
      setSelectedDoc(null);
      setSelectedDetail(null);
      setRejectReason('');
      fetchVerifications();
    } catch (err: any) {
      toast.error(err.message || 'Failed to reject seller.');
    } finally {
      setIsActionLoading(false);
    }
  };

  if (!isAuthenticated || !user || user.role !== 'admin') return null;

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold flex items-center gap-2">
              <Shield className="w-7 h-7 text-primary" /> Seller Verifications
            </h1>
            <p className="text-muted-foreground mt-1">Review identity and store setups to ensure marketplace trust.</p>
          </div>
          <Button variant="outline" className="gap-2 shrink-0" onClick={() => router.push(routes.adminDashboard())}>
            <ArrowUpRight className="w-4 h-4" /> Dashboard
          </Button>
        </motion.div>

        <Card className="border-0 shadow-md">
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg">Verification Queue</CardTitle>
              <CardDescription>{totalCount} total requests</CardDescription>
            </div>
            <Badge variant="secondary" className="bg-primary/20 text-primary uppercase text-xs">
              {activeTab}
            </Badge>
          </CardHeader>
          <CardContent>
            <Tabs value={activeTab} onValueChange={(val) => { setActiveTab(val); setPage(1); }}>
              <TabsList className="mb-4">
                <TabsTrigger value="pending" className="gap-1.5"><Clock className="w-4 h-4" /> Pending Review</TabsTrigger>
                <TabsTrigger value="approved" className="gap-1.5"><CheckCircle2 className="w-4 h-4" /> Approved</TabsTrigger>
                <TabsTrigger value="rejected" className="gap-1.5"><XCircle className="w-4 h-4" /> Rejected</TabsTrigger>
              </TabsList>

              <TabsContent value={activeTab}>
                {isLoading ? (
                  <div className="space-y-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 w-full" />)}</div>
                ) : verifications.length === 0 ? (
                  <div className="text-center py-16 text-muted-foreground">
                    <CheckCircle2 className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <h3 className="font-semibold text-foreground text-lg mb-1">Catch up complete!</h3>
                    <p className="text-sm">There are no {activeTab} verify requests at the moment.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {verifications.map((v) => (
                      <div key={v.id} className="border rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                          <Avatar className="h-12 w-12"><AvatarFallback><User className="w-5 h-5" /></AvatarFallback></Avatar>
                          <div>
                            <p className="font-semibold text-sm">Seller ID: #{v.id}</p>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge variant="outline" className="text-[10px]">{v.id_type || 'Identity'}</Badge>
                              <span className="text-xs text-muted-foreground">{v.user?.email}</span>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center justify-between sm:justify-end gap-6 w-full sm:w-auto">
                          <div className="text-right">
                            <p className="text-xs text-muted-foreground font-medium">Submitted</p>
                            <p className="text-xs">{v.identity_submitted_at ? getRelativeTime(v.identity_submitted_at) : 'N/A'}</p>
                          </div>
                          <Button size="sm" onClick={() => handleReview(v)} className="gap-1.5">
                            <Eye className="w-4 h-4" /> Review
                          </Button>
                        </div>
                      </div>
                    ))}

                    {totalPages > 1 && (
                      <div className="flex items-center justify-between mt-4 pt-4 border-t">
                        <p className="text-sm text-muted-foreground">Page {page} of {totalPages}</p>
                        <div className="flex items-center gap-2">
                          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="w-4 h-4" /> Prev</Button>
                          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next <ChevronRight className="w-4 h-4" /></Button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Review Dialog */}
        <Dialog open={!!selectedDoc} onOpenChange={(open) => { if(!open) { setSelectedDoc(null); setSelectedDetail(null); } }}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Review Seller #{selectedDoc?.id}</DialogTitle>
            </DialogHeader>
            {isDetailLoading ? (
               <div className="py-20 flex flex-col items-center justify-center space-y-4">
                 <Loader2 className="w-10 h-10 animate-spin text-primary" />
                 <p className="text-sm text-muted-foreground">Loading seller documents...</p>
               </div>
            ) : selectedDetail ? (
              <div className="space-y-6 pt-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  <div className="space-y-2">
                     <p className="text-sm font-semibold">National ID / Document</p>
                     <p className="text-xs text-muted-foreground">
                        {selectedDetail.identity_verification?.id_type} - {selectedDetail.identity_verification?.id_number}
                     </p>
                     <div className="aspect-video relative rounded-lg border overflow-hidden bg-muted">
                        {selectedDetail.identity_verification?.id_front_image ? (
                           <img src={selectedDetail.identity_verification.id_front_image} alt="ID" className="absolute inset-0 w-full h-full object-contain" />
                        ) : (
                           <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-xs">No image provided</div>
                        )}
                     </div>
                  </div>
                  <div className="space-y-2">
                     <p className="text-sm font-semibold">Selfie with ID</p>
                     <p className="text-xs text-muted-foreground">Verification photo</p>
                     <div className="aspect-video relative rounded-lg border overflow-hidden bg-muted">
                        {selectedDetail.identity_verification?.selfie_with_id ? (
                           <img src={selectedDetail.identity_verification.selfie_with_id} alt="Selfie" className="absolute inset-0 w-full h-full object-contain" />
                        ) : (
                           <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-xs">No selfie provided</div>
                        )}
                     </div>
                  </div>
                </div>

                <div className="bg-muted/30 p-4 rounded-lg space-y-2">
                   <p className="text-sm font-semibold">Store Information</p>
                   <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                      <span className="text-muted-foreground">Store Name:</span>
                      <span className="font-medium">{selectedDetail.store_name}</span>
                      <span className="text-muted-foreground">Location:</span>
                      <span className="font-medium">{selectedDetail.store_location}</span>
                      <span className="text-muted-foreground">Seller:</span>
                      <span className="font-medium">{selectedDetail.user?.username} ({selectedDetail.user?.email})</span>
                   </div>
                </div>

                {selectedDetail.verification_status === 'under_review' && (
                  <div className="space-y-4 pt-4 border-t">
                    <p className="font-semibold text-sm">Review Decision</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <Button onClick={onApprove} disabled={isActionLoading} className="bg-green-600 hover:bg-green-700 h-11">
                        {isActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <><CheckCircle2 className="w-4 h-4 mr-2" /> Approve Seller</>}
                      </Button>
                      
                      <Dialog>
                         <Tabs defaultValue="approve" className="w-full">
                            <Button variant="outline" className="w-full h-11 text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200" onClick={() => {}}>
                               <XCircle className="w-4 h-4 mr-2" /> Reject Submission
                            </Button>
                         </Tabs>
                      </Dialog>
                    </div>

                    <div className="bg-red-50 dark:bg-red-900/10 p-4 rounded-xl border border-red-100 dark:border-red-900/30 space-y-3">
                        <Label className="text-xs font-bold text-red-800 dark:text-red-400 uppercase">Rejection Reason</Label>
                        <Textarea 
                          placeholder="e.g. ID is expired, Photo is blurry, Please retake selfie..." 
                          value={rejectReason} 
                          onChange={e => setRejectReason(e.target.value)}
                          className="bg-white dark:bg-black/20"
                        />
                        <Button 
                          variant="destructive" 
                          className="w-full h-11" 
                          onClick={onReject} 
                          disabled={isActionLoading || !rejectReason.trim()}
                        >
                          <XCircle className="w-4 h-4 mr-2" /> Confirm Rejection
                        </Button>
                    </div>
                  </div>
                )}
                
                {selectedDetail.verification_status !== 'under_review' && (
                  <div className="pt-4 border-t flex items-center justify-between">
                    <div>
                        <p className="text-xs text-muted-foreground font-medium uppercase mb-1">Current Status</p>
                        <Badge variant="outline" className={`${selectedDetail.verification_status === 'verified' ? 'text-green-600 border-green-600 bg-green-50' : 'text-red-600 border-red-600 bg-red-50'} uppercase py-1 px-3`}>
                            {selectedDetail.verification_status}
                        </Badge>
                    </div>
                    {selectedDetail.identity_verification?.rejection_reason && (
                       <div className="text-right">
                          <p className="text-xs text-red-600 font-semibold italic">"{selectedDetail.identity_verification.rejection_reason}"</p>
                       </div>
                    )}
                  </div>
                )}
              </div>
            ) : null}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
