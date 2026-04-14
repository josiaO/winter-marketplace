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
  const [activeQueue, setActiveQueue] = useState('identity'); // identity, business
  const [statusFilter, setStatusFilter] = useState('pending'); // pending, approved, rejected (though we mostly care about pending)
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
        queue: activeQueue,
        status: statusFilter,
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
  }, [activeQueue, statusFilter, page]);

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

  const onApproveIdentity = async () => {
    if (!selectedDoc) return;
    setIsActionLoading(true);
    try {
      await api.sellers.adminVerifyApprove(selectedDoc.id);
      toast.success('Identity approved.');
      handleRefreshReview();
    } catch (err: any) {
      toast.error(err.message || 'Failed to approve.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const onApproveBusiness = async () => {
    if (!selectedDoc) return;
    setIsActionLoading(true);
    try {
      await api.sellers.adminVerifyBusinessApprove(selectedDoc.id);
      toast.success('Business upgrade approved.');
      handleRefreshReview();
    } catch (err: any) {
      toast.error(err.message || 'Failed to approve business.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const onReject = async (type: 'identity' | 'business') => {
    if (!selectedDoc) return;
    if (!rejectReason.trim()) return toast.error('Please provide a reason.');
    setIsActionLoading(true);
    try {
      if (type === 'identity') {
        await api.sellers.adminVerifyReject(selectedDoc.id, { reason: rejectReason });
      } else {
        await api.sellers.adminVerifyBusinessReject(selectedDoc.id, { reason: rejectReason });
      }
      toast.success('Application rejected.');
      handleRefreshReview();
    } catch (err: any) {
      toast.error(err.message || 'Failed to reject.');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRefreshReview = async () => {
    if (!selectedDoc) return;
    try {
        const detail = await api.sellers.adminSellerDetail(selectedDoc.id);
        setSelectedDetail(detail);
        setRejectReason('');
        fetchVerifications();
      } catch {
        setSelectedDoc(null);
        setSelectedDetail(null);
      }
  }

  if (!isAuthenticated || !user || user.role !== 'admin') return null;

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  return (
    <div className="min-h-[80vh] px-4 py-8 bg-[#f9fafb]">
      <div className="max-w-7xl mx-auto space-y-8">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-gray-900 flex items-center gap-3">
              <Shield className="w-8 h-8 text-primary" /> Seller Control Center
            </h1>
            <p className="text-muted-foreground mt-1.5 text-lg">Manage multi-tier verification and marketplace security.</p>
          </div>
          <div className="flex items-center gap-3">
             <Button variant="outline" className="gap-2 shrink-0 h-11" onClick={() => router.push(routes.adminDashboard())}>
                <ArrowUpRight className="w-4 h-4" /> Dashboard
             </Button>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
            <div className="lg:col-span-1 space-y-6">
                <Card className="border-0 shadow-sm overflow-hidden">
                    <CardHeader className="bg-gray-50/50 border-b">
                        <CardTitle className="text-sm font-bold uppercase tracking-wider text-gray-500">Categories</CardTitle>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="flex flex-col">
                            <button 
                                onClick={() => { setActiveQueue('identity'); setPage(1); }}
                                className={`flex items-center justify-between p-4 text-sm font-medium transition-colors ${activeQueue === 'identity' ? 'bg-primary/5 text-primary border-r-4 border-primary' : 'hover:bg-gray-50 text-gray-600'}`}
                            >
                                <div className="flex items-center gap-3">
                                    <User className="w-4 h-4" /> Identity Verification
                                </div>
                                {activeQueue === 'identity' && <Badge variant="secondary" className="bg-primary/10 text-primary">{totalCount}</Badge>}
                            </button>
                            <button 
                                onClick={() => { setActiveQueue('business'); setPage(1); }}
                                className={`flex items-center justify-between p-4 text-sm font-medium transition-colors ${activeQueue === 'business' ? 'bg-primary/5 text-primary border-r-4 border-primary' : 'hover:bg-gray-50 text-gray-600'}`}
                            >
                                <div className="flex items-center gap-3">
                                    <Briefcase className="w-4 h-4" /> Business Upgrades
                                </div>
                                {activeQueue === 'business' && <Badge variant="secondary" className="bg-primary/10 text-primary">{totalCount}</Badge>}
                            </button>
                        </div>
                    </CardContent>
                </Card>

                <div className="bg-primary/5 rounded-2xl p-6 space-y-4">
                    <h4 className="font-bold text-primary flex items-center gap-2">
                        <Clock className="w-5 h-5" /> Queue Status
                    </h4>
                    <div className="grid grid-cols-1 gap-2">
                        {['pending', 'approved', 'rejected'].map((s) => (
                            <button 
                                key={s}
                                onClick={() => setStatusFilter(s)}
                                className={`px-4 py-2.5 rounded-xl text-sm font-semibold capitalize transition-all ${statusFilter === s ? 'bg-primary text-white shadow-lg shadow-primary/20' : 'bg-white text-gray-600 hover:bg-gray-100'}`}
                            >
                                {s}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <div className="lg:col-span-3">
                <Card className="border-0 shadow-sm min-h-[500px]">
                    <CardContent className="p-6">
                        {isLoading ? (
                            <div className="space-y-6 pt-4">
                                {Array.from({ length: 5 }).map((_, i) => (
                                    <div key={i} className="flex items-center gap-4">
                                        <Skeleton className="h-14 w-14 rounded-full" />
                                        <div className="space-y-2 flex-1">
                                            <Skeleton className="h-4 w-1/4" />
                                            <Skeleton className="h-3 w-1/2" />
                                        </div>
                                        <Skeleton className="h-10 w-24 rounded-xl" />
                                    </div>
                                ))}
                            </div>
                        ) : verifications.length === 0 ? (
                            <div className="flex flex-col items-center justify-center py-32 text-center text-muted-foreground">
                                <CheckCircle2 className="w-16 h-16 mb-4 opacity-20 text-green-600" />
                                <h3 className="text-xl font-bold text-gray-900">Queue is empty</h3>
                                <p className="mt-2 max-w-xs mx-auto">All {activeQueue} {statusFilter} requests have been processed.</p>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {verifications.map((v) => (
                                    <motion.div 
                                        key={v.id} 
                                        initial={{ opacity: 0 }} 
                                        animate={{ opacity: 1 }}
                                        className="group bg-white hover:bg-gray-50 border rounded-2xl p-5 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                                    >
                                        <div className="flex items-center gap-5">
                                            <Avatar className="h-14 w-14 ring-4 ring-gray-50">
                                                <AvatarFallback className="bg-primary/5 text-primary font-bold text-lg">
                                                    {v.store_name?.charAt(0) || <User className="w-6 h-6" />}
                                                </AvatarFallback>
                                            </Avatar>
                                            <div>
                                                <h4 className="font-bold text-gray-900 group-hover:text-primary transition-colors">
                                                    {v.store_name || "New Seller Registration"}
                                                </h4>
                                                <div className="flex flex-wrap items-center gap-2 mt-1.5">
                                                    <Badge variant="outline" className="bg-gray-50 text-[10px] font-bold uppercase tracking-wider">#{v.id}</Badge>
                                                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                                                        <Clock className="w-3 h-3" /> 
                                                        {activeQueue === 'identity' ? getRelativeTime(v.identity_submitted_at) : getRelativeTime(v.business_submitted_at)}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-4 ml-auto sm:ml-0">
                                            <div className="text-right hidden md:block">
                                                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Email</p>
                                                <p className="text-xs font-medium text-gray-600">{v.user?.email}</p>
                                            </div>
                                            <Button onClick={() => handleReview(v)} variant="secondary" className="rounded-xl font-bold h-11 px-6 shadow-sm hover:shadow-md transition-all gap-2">
                                               <Eye className="w-4 h-4" /> Review
                                            </Button>
                                        </div>
                                    </motion.div>
                                ))}
                                
                                {totalPages > 1 && (
                                    <div className="flex items-center justify-between mt-8 pt-6 border-t">
                                        <p className="text-sm font-medium text-gray-500">Page {page} of {totalPages}</p>
                                        <div className="flex items-center gap-3">
                                            <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="rounded-lg h-10 px-4">
                                                <ChevronLeft className="w-4 h-4 mr-2" /> Prev
                                            </Button>
                                            <Button variant="ghost" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} className="rounded-lg h-10 px-4">
                                                Next <ChevronRight className="w-4 h-4 ml-2" />
                                            </Button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>

        {/* Review Dialog Content */}
        <Dialog open={!!selectedDoc} onOpenChange={(open) => { if(!open) { setSelectedDoc(null); setSelectedDetail(null); } }}>
          <DialogContent className="max-w-4xl max-h-[95vh] p-0 overflow-hidden border-0 shadow-2xl rounded-3xl">
            {isDetailLoading ? (
               <div className="py-32 flex flex-col items-center justify-center space-y-6">
                 <div className="relative">
                    <Loader2 className="w-12 h-12 animate-spin text-primary" />
                    <Shield className="w-5 h-5 text-primary absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
                 </div>
                 <p className="text-lg font-bold text-gray-900 animate-pulse">Scanning seller documents...</p>
               </div>
            ) : selectedDetail ? (
              <div className="flex flex-col h-full bg-slate-50">
                <div className="bg-white border-b px-8 py-6 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Avatar className="h-16 w-16">
                            <AvatarFallback className="bg-primary text-white font-bold text-2xl uppercase">
                                {selectedDetail.store_name?.charAt(0)}
                            </AvatarFallback>
                        </Avatar>
                        <div>
                            <DialogTitle className="text-2xl font-black text-gray-900">{selectedDetail.store_name}</DialogTitle>
                            <p className="text-sm text-muted-foreground flex items-center gap-2 mt-0.5">
                                <Badge variant="secondary" className="font-bold">SELLER #{selectedDetail.id}</Badge>
                                <span>•</span>
                                <span>Joined {getRelativeTime(selectedDetail.user?.date_joined || new Date())}</span>
                            </p>
                        </div>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto px-8 py-6 space-y-8">
                    {/* Security Analysis Section */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <Card className="bg-emerald-50 border-emerald-100 shadow-none">
                            <CardContent className="p-4 flex items-center gap-4 text-emerald-900">
                                <CheckCircle2 className="w-10 h-10 opacity-40 shrink-0" />
                                <div>
                                    <p className="text-[10px] uppercase font-black opacity-60">Completed Orders</p>
                                    <p className="text-2xl font-black">{selectedDetail.completed_orders || 0}</p>
                                </div>
                            </CardContent>
                        </Card>
                        <Card className="bg-blue-50 border-blue-100 shadow-none">
                            <CardContent className="p-4 flex items-center gap-4 text-blue-900">
                                <Briefcase className="w-10 h-10 opacity-40 shrink-0" />
                                <div>
                                    <p className="text-[10px] uppercase font-black opacity-60">Total Sales (GMV)</p>
                                    <p className="text-2xl font-black">TZS {new Intl.NumberFormat().format(selectedDetail.total_sales || 0)}</p>
                                </div>
                            </CardContent>
                        </Card>
                         <Card className="bg-indigo-50 border-indigo-100 shadow-none">
                            <CardContent className="p-4 flex items-center gap-4 text-indigo-900">
                                <Shield className="w-10 h-10 opacity-40 shrink-0" />
                                <div>
                                    <p className="text-[10px] uppercase font-black opacity-60">Listing Status</p>
                                    <p className="text-2xl font-black">{selectedDetail.is_active ? 'Public' : 'Hidden'}</p>
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        {/* Evidence Panel */}
                        <div className="space-y-6">
                            <h3 className="text-lg font-black text-gray-900 flex items-center gap-2">
                                <ImageIcon className="w-5 h-5 text-gray-400" /> Evidence Logs
                            </h3>
                            
                            {activeQueue === 'identity' ? (
                                <div className="space-y-4">
                                     <div className="space-y-2">
                                        <Label className="text-xs font-bold uppercase text-gray-500">
                                            {selectedDetail.identity_verification?.id_type} Front
                                        </Label>
                                        <div className="aspect-video relative rounded-2xl border-2 border-dashed border-gray-200 overflow-hidden bg-white group cursor-zoom-in">
                                            {selectedDetail.identity_verification?.id_front_image ? (
                                            <img 
                                                src={selectedDetail.identity_verification.id_front_image} 
                                                alt="ID Front" 
                                                onClick={() => window.open(selectedDetail.identity_verification.id_front_image, '_blank')}
                                                className="absolute inset-0 w-full h-full object-contain p-2 group-hover:scale-105 transition-transform" 
                                            />
                                            ) : (
                                            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-xs italic">Front doc missing</div>
                                            )}
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <Label className="text-xs font-bold uppercase text-gray-500">Selfie Match</Label>
                                        <div className="aspect-video relative rounded-2xl border-2 border-dashed border-gray-200 overflow-hidden bg-white group cursor-zoom-in">
                                            {selectedDetail.identity_verification?.selfie_with_id ? (
                                            <img 
                                                src={selectedDetail.identity_verification.selfie_with_id} 
                                                alt="Selfie" 
                                                onClick={() => window.open(selectedDetail.identity_verification.selfie_with_id, '_blank')}
                                                className="absolute inset-0 w-full h-full object-contain p-2 group-hover:scale-105 transition-transform" 
                                            />
                                            ) : (
                                            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-xs italic">Selfie missing</div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                     <div className="space-y-2">
                                        <Label className="text-xs font-bold uppercase text-gray-500">TIN Certificate</Label>
                                        <div className="aspect-video relative rounded-2xl border-2 border-dashed border-gray-200 overflow-hidden bg-white group cursor-zoom-in">
                                            {selectedDetail.business_verification?.tin_certificate ? (
                                            <img 
                                                src={selectedDetail.business_verification.tin_certificate} 
                                                alt="TIN" 
                                                onClick={() => window.open(selectedDetail.business_verification.tin_certificate, '_blank')}
                                                className="absolute inset-0 w-full h-full object-contain p-2 group-hover:scale-105 transition-transform" 
                                            />
                                            ) : (
                                            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-xs italic">TIN missing</div>
                                            )}
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <Label className="text-xs font-bold uppercase text-gray-500">Business License</Label>
                                        <div className="aspect-video relative rounded-2xl border-2 border-dashed border-gray-200 overflow-hidden bg-white group cursor-zoom-in">
                                            {selectedDetail.business_verification?.business_license_document ? (
                                            <img 
                                                src={selectedDetail.business_verification.business_license_document} 
                                                alt="License" 
                                                onClick={() => window.open(selectedDetail.business_verification.business_license_document, '_blank')}
                                                className="absolute inset-0 w-full h-full object-contain p-2 group-hover:scale-105 transition-transform" 
                                            />
                                            ) : (
                                            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-xs italic">License missing</div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Controls Panel */}
                        <div className="space-y-6">
                            <h3 className="text-lg font-black text-gray-900 flex items-center gap-2">
                                <Clock className="w-5 h-5 text-gray-400" /> Moderation Log
                            </h3>
                            
                            <div className="bg-white rounded-3xl p-6 border shadow-sm space-y-6">
                                <div>
                                    <Label className="text-xs font-bold text-gray-500 uppercase">Review Feedback</Label>
                                    <Textarea 
                                        placeholder={activeQueue === 'identity' ? "Notes for identity..." : "Notes for business upgrade..."}
                                        value={rejectReason} 
                                        onChange={e => setRejectReason(e.target.value)}
                                        className="mt-2 min-h-[100px] border-none bg-slate-50 focus-visible:ring-primary rounded-2xl p-4"
                                    />
                                </div>

                                <div className="space-y-3">
                                    {(activeQueue === 'identity' && selectedDetail.identity_verification?.status === 'pending') && (
                                        <div className="flex flex-col gap-3">
                                            <Button onClick={onApproveIdentity} disabled={isActionLoading} className="w-full bg-emerald-600 hover:bg-emerald-700 h-14 rounded-2xl text-lg font-bold shadow-lg shadow-emerald-200 transition-all">
                                                {isActionLoading ? <Loader2 className="w-6 h-6 animate-spin text-white" /> : "Approve Identity"}
                                            </Button>
                                            <Button variant="outline" onClick={() => onReject('identity')} disabled={isActionLoading || !rejectReason.trim()} className="w-full h-14 rounded-2xl text-red-600 border-red-100 hover:bg-red-50 hover:text-red-700 font-bold">
                                                Reject Identity
                                            </Button>
                                        </div>
                                    )}

                                    {(activeQueue === 'business' && (selectedDetail.business_verification?.tin_status === 'pending' || selectedDetail.business_verification?.business_license_status === 'pending')) && (
                                        <div className="flex flex-col gap-3">
                                            <Button onClick={onApproveBusiness} disabled={isActionLoading} className="w-full bg-indigo-600 hover:bg-indigo-700 h-14 rounded-2xl text-lg font-bold shadow-lg shadow-indigo-200 transition-all">
                                                {isActionLoading ? <Loader2 className="w-6 h-6 animate-spin text-white" /> : "Approve Business Upgrade"}
                                            </Button>
                                            <Button variant="outline" onClick={() => onReject('business')} disabled={isActionLoading || !rejectReason.trim()} className="w-full h-14 rounded-2xl text-red-600 border-red-100 hover:bg-red-50 hover:text-red-700 font-bold">
                                                Reject Upgrade
                                            </Button>
                                        </div>
                                    )}

                                    {selectedDetail.verification_status === 'verified' && (
                                         <Badge className="w-full h-12 flex items-center justify-center bg-emerald-100 text-emerald-800 border-0 rounded-2xl font-black uppercase text-sm">
                                            Identity Currently Verified
                                         </Badge>
                                    )}
                                </div>
                            </div>

                            <Card className="border-0 bg-transparent shadow-none">
                                <CardHeader className="p-0 pb-3">
                                    <p className="text-xs font-bold text-gray-500 uppercase">Recent Activity</p>
                                </CardHeader>
                                <CardContent className="p-0">
                                    <div className="space-y-3">
                                        {selectedDetail.action_logs?.slice(0, 3).map((log: any) => (
                                            <div key={log.id} className="flex items-start gap-3 text-xs">
                                                <div className="w-2 h-2 rounded-full bg-gray-300 mt-1.5" />
                                                <div className="flex-1">
                                                    <p className="font-bold text-gray-700 capitalize">{log.action}</p>
                                                    <p className="text-gray-500 italic">"{log.reason || 'No comment provided'}"</p>
                                                    <p className="text-[10px] text-gray-400 mt-1">{getRelativeTime(log.timestamp)} by {log.performed_by_username}</p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    </div>
                </div>
              </div>
            ) : null}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
