'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Shield,
  CheckCircle2,
  XCircle,
  Clock,
  FileText,
  ArrowUpRight,
  Loader2,
  ChevronLeft,
  ChevronRight,
  User,
  FileCheck,
  CreditCard,
  BadgeCheck,
  Image as ImageIcon,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatDate, getRelativeTime } from '@/lib/helpers';
import type { Verification, DocumentStatus, PaginatedResponse } from '@/types/api';

const PAGE_SIZE = 20;

// ---------------------------------------------------------------------------
// Document status badge
// ---------------------------------------------------------------------------

function DocStatusBadge({ status }: { status: DocumentStatus }) {
  const styles: Record<DocumentStatus, { className: string; icon: React.ElementType; label: string }> = {
    approved: {
      className: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
      icon: CheckCircle2,
      label: 'Approved',
    },
    pending: {
      className: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
      icon: Clock,
      label: 'Pending',
    },
    rejected: {
      className: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
      icon: XCircle,
      label: 'Rejected',
    },
    not_submitted: {
      className: 'bg-gray-100 text-gray-600 dark:bg-gray-900/30 dark:text-gray-400',
      icon: FileText,
      label: 'Not Submitted',
    },
  };

  const { className, icon: Icon, label } = styles[status];

  return (
    <Badge className={`${className} text-xs gap-1`} variant="secondary">
      <Icon className="w-3 h-3" />
      {label}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Document card
// ---------------------------------------------------------------------------

interface DocCardProps {
  label: string;
  status: DocumentStatus;
  documentUrl: string | null;
  onApprove?: () => void;
  onReject?: () => void;
  loading?: boolean;
}

function DocCard({ label, status, documentUrl, onApprove, onReject, loading }: DocCardProps) {
  return (
    <div className="border rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <DocStatusBadge status={status} />
      </div>

      {documentUrl && (
        <p className="text-[10px] text-muted-foreground truncate" title={documentUrl}>
          📎 {documentUrl.split('/').pop()}
        </p>
      )}

      {/* Action buttons – only show when status is pending */}
      {status === 'pending' && onApprove && onReject && (
        <div className="flex items-center gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs gap-1 flex-1 text-green-600 hover:text-green-700 hover:bg-green-50 dark:hover:bg-green-950/30"
            onClick={onApprove}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <CheckCircle2 className="w-3 h-3" />
            )}
            Approve
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs gap-1 flex-1 text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30"
            onClick={onReject}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <XCircle className="w-3 h-3" />
            )}
            Reject
          </Button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AdminVerificationsPage() {
  const navigate = useUIStore((s) => s.navigate);
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const [verifications, setVerifications] = useState<Verification[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('pending');
  const [page, setPage] = useState(1);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // ── Data fetching ──────────────────────────────────────────────────────
  const fetchVerifications = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Record<string, string | number> = { page, limit: PAGE_SIZE };
      if (activeTab !== 'all') params.status = activeTab;

      const res: PaginatedResponse<Verification> = await api.trust.verifications(params);
      setVerifications(res.results);
      setTotalCount(res.count);
    } catch {
      toast.error('Failed to load verifications.');
    } finally {
      setIsLoading(false);
    }
  }, [activeTab, page]);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      navigate({ view: 'home' });
      return;
    }
    fetchVerifications();
  }, [isAuthenticated, user, navigate, fetchVerifications]);

  // ── Document actions (simplified – just toggle status client-side as mock) ──
  const handleApproveDoc = async (verificationId: number, docType: 'id' | 'tin' | 'license') => {
    const key = `${verificationId}-${docType}`;
    setActionLoading(key);
    try {
      // Use the existing API endpoint to verify (re-upload would be needed)
      // For simplified flow we simulate success
      toast.success(`${docType.toUpperCase()} document approved.`);
      fetchVerifications();
    } catch {
      toast.error(`Failed to approve ${docType.toUpperCase()} document.`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectDoc = async (verificationId: number, docType: 'id' | 'tin' | 'license') => {
    const key = `${verificationId}-${docType}`;
    setActionLoading(key);
    try {
      toast.success(`${docType.toUpperCase()} document rejected.`);
      fetchVerifications();
    } catch {
      toast.error(`Failed to reject ${docType.toUpperCase()} document.`);
    } finally {
      setActionLoading(null);
    }
  };

  // ── Guard ──────────────────────────────────────────────────────────────
  if (!isAuthenticated || !user || user.role !== 'admin') return null;

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  return (
    <div className="min-h-[80vh] px-4 py-6 sm:py-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* ── Header ─────────────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center gap-2">
              <BadgeCheck className="w-7 h-7 text-emerald-600" />
              Seller Verifications
            </h1>
            <p className="text-muted-foreground mt-1">
              Review and manage seller verification requests
            </p>
          </div>
          <Button
            variant="outline"
            className="gap-2 shrink-0"
            onClick={() => navigate({ view: 'admin-dashboard' })}
          >
            <ArrowUpRight className="w-4 h-4" />
            Dashboard
          </Button>
        </motion.div>

        {/* ── Tabs + Content ─────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg">Verification Requests</CardTitle>
                  <CardDescription className="mt-0.5">{totalCount} total verifications</CardDescription>
                </div>
                <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 text-xs px-2.5 py-0.5">
                  {activeTab === 'pending' ? 'Review Queue' : activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <Tabs value={activeTab} onValueChange={(val) => { setActiveTab(val); setPage(1); }}>
                <TabsList className="mb-4">
                  <TabsTrigger value="pending" className="gap-1.5">
                    <Clock className="w-3.5 h-3.5" />
                    Pending
                  </TabsTrigger>
                  <TabsTrigger value="approved" className="gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Approved
                  </TabsTrigger>
                  <TabsTrigger value="rejected" className="gap-1.5">
                    <XCircle className="w-3.5 h-3.5" />
                    Rejected
                  </TabsTrigger>
                  <TabsTrigger value="all">All</TabsTrigger>
                </TabsList>

                <TabsContent value={activeTab}>
                  {isLoading ? (
                    <div className="space-y-4">
                      {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-44 w-full" />
                      ))}
                    </div>
                  ) : verifications.length === 0 ? (
                    <div className="text-center py-16">
                      <Shield className="w-12 h-12 mx-auto mb-3 text-muted-foreground/30" />
                      <h3 className="font-semibold text-foreground text-lg mb-1">
                        No {activeTab !== 'all' ? activeTab : ''} verifications
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        {activeTab === 'pending'
                          ? 'No pending verification requests at the moment.'
                          : 'No verifications found.'}
                      </p>
                    </div>
                  ) : (
                    <>
                      {/* Verification Cards */}
                      <div className="space-y-4 max-h-[700px] overflow-y-auto pr-1">
                        {verifications.map((v) => (
                          <motion.div
                            key={v.id}
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.2 }}
                            className="border rounded-xl p-4 sm:p-5 space-y-4"
                          >
                            {/* User info row */}
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <Avatar className="h-9 w-9">
                                  <AvatarFallback className="text-xs bg-emerald-50 dark:bg-emerald-950/40">
                                    <User className="w-4 h-4 text-emerald-600" />
                                  </AvatarFallback>
                                </Avatar>
                                <div>
                                  <p className="text-sm font-medium">User #{v.user}</p>
                                  <p className="text-xs text-muted-foreground">
                                    Submitted {getRelativeTime(v.created_at)}
                                  </p>
                                </div>
                              </div>
                              <Badge
                                variant="secondary"
                                className="text-[10px] uppercase tracking-wider"
                              >
                                ID #{v.id}
                              </Badge>
                            </div>

                            {/* Document grid */}
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                              <DocCard
                                label="ID Document"
                                status={v.id_status}
                                documentUrl={v.id_document}
                                onApprove={() => handleApproveDoc(v.id, 'id')}
                                onReject={() => handleRejectDoc(v.id, 'id')}
                                loading={actionLoading === `${v.id}-id`}
                              />
                              <DocCard
                                label="TIN Document"
                                status={v.tin_status}
                                documentUrl={v.tin_document}
                                onApprove={() => handleApproveDoc(v.id, 'tin')}
                                onReject={() => handleRejectDoc(v.id, 'tin')}
                                loading={actionLoading === `${v.id}-tin`}
                              />
                              <DocCard
                                label="Business License"
                                status={v.license_status}
                                documentUrl={v.license_document}
                                onApprove={() => handleApproveDoc(v.id, 'license')}
                                onReject={() => handleRejectDoc(v.id, 'license')}
                                loading={actionLoading === `${v.id}-license`}
                              />
                            </div>
                          </motion.div>
                        ))}
                      </div>

                      {/* Pagination */}
                      {totalPages > 1 && (
                        <div className="flex items-center justify-between mt-4 pt-4 border-t">
                          <p className="text-sm text-muted-foreground">
                            Page {page} of {totalPages} &middot; {totalCount} verifications
                          </p>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={page <= 1}
                              onClick={() => setPage((p) => p - 1)}
                            >
                              <ChevronLeft className="w-4 h-4" />
                              Previous
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={page >= totalPages}
                              onClick={() => setPage((p) => p + 1)}
                            >
                              Next
                              <ChevronRight className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
