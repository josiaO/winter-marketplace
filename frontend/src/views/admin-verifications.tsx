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

  // Review Dialog State
  const [selectedDoc, setSelectedDoc] = useState<any | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [isActionLoading, setIsActionLoading] = useState(false);

  const fetchVerifications = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: any = { page, page_size: PAGE_SIZE, status: activeTab };
      const res = await api.sellers.adminVerifications(params);
      setVerifications(res.results || []);
      setTotalCount(res.count || 0);
    } catch {
      toast.error('Failed to load verifications.');
    } finally {
      setIsLoading(false);
    }
  }, [activeTab, page]);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      router.push(routes.home());
      return;
    }
    fetchVerifications();
  }, [isAuthenticated, user, router, fetchVerifications]);

  const onApprove = async () => {
    if (!selectedDoc) return;
    setIsActionLoading(true);
    try {
      await api.sellers.adminVerifyApprove(selectedDoc.id);
      toast.success('Seller approved successfully.');
      setSelectedDoc(null);
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
                            <p className="font-semibold text-sm">Seller ID: #{v.seller}</p>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge variant="outline" className="text-[10px]">{v.id_type}</Badge>
                              <span className="text-xs text-muted-foreground">{v.id_number}</span>
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center justify-between sm:justify-end gap-6 w-full sm:w-auto">
                          <div className="text-right">
                            <p className="text-xs text-muted-foreground font-medium">Submitted</p>
                            <p className="text-xs">{getRelativeTime(v.submitted_at)}</p>
                          </div>
                          <Button size="sm" onClick={() => setSelectedDoc(v)} className="gap-1.5">
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
        <Dialog open={!!selectedDoc} onOpenChange={(open) => { if(!open) setSelectedDoc(null); }}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Review Document #{selectedDoc?.id}</DialogTitle>
            </DialogHeader>
            {selectedDoc && (
              <div className="space-y-6 pt-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                     <p className="text-sm font-semibold">National ID / Document</p>
                     <p className="text-xs text-muted-foreground">{selectedDoc.id_type} - {selectedDoc.id_number}</p>
                     <img src={selectedDoc.id_front_image || '/placeholder-image.jpg'} alt="ID" className="w-full h-auto rounded-lg border object-cover" />
                  </div>
                  <div className="space-y-2">
                     <p className="text-sm font-semibold">Selfie with ID</p>
                     <p className="text-xs text-muted-foreground">Match face with ID document</p>
                     <img src={selectedDoc.selfie_with_id || '/placeholder-image.jpg'} alt="Selfie" className="w-full h-auto rounded-lg border object-cover" />
                  </div>
                </div>

                {selectedDoc.status === 'pending' && (
                  <div className="space-y-4 pt-4 border-t">
                    <p className="font-semibold text-sm">Action Requirement</p>
                    <div className="flex flex-col gap-3">
                      <Button onClick={onApprove} disabled={isActionLoading} className="w-full h-12 bg-green-600 hover:bg-green-700">
                        {isActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <><CheckCircle2 className="w-4 h-4 mr-2" /> Approve Verification</>}
                      </Button>
                      
                      <div className="space-y-2 mt-4">
                         <p className="text-xs font-semibold">Reject Document?</p>
                         <Textarea placeholder="Indicate reason for rejection (e.g. Blurry photo, ID expired)" value={rejectReason} onChange={e => setRejectReason(e.target.value)} />
                         <Button variant="destructive" className="w-full" onClick={onReject} disabled={isActionLoading || !rejectReason.trim()}>
                            <XCircle className="w-4 h-4 mr-2" /> Reject & Request Resubmission
                         </Button>
                      </div>
                    </div>
                  </div>
                )}
                {selectedDoc.status !== 'pending' && (
                  <div className="pt-4 border-t">
                    <Badge variant="outline" className={`${selectedDoc.status === 'approved' ? 'text-green-600 border-green-600' : 'text-red-600 border-red-600'} uppercase py-1 px-3`}>
                      {selectedDoc.status}
                    </Badge>
                    {selectedDoc.rejection_reason && (
                       <p className="mt-2 text-sm text-red-600 dark:text-red-400">Reason: {selectedDoc.rejection_reason}</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
