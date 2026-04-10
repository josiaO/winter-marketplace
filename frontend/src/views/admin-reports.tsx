'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  ArrowUpRight,
  Loader2,
  CheckCircle2,
  XCircle,
  ChevronLeft,
  ChevronRight,
  Eye,
  Shield,
  Flag,
  Clock,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatDate, getRelativeTime } from '@/lib/helpers';
import type { Report, ReportStatus, PaginatedResponse } from '@/types/api';

const PAGE_SIZE = 20;

// ---------------------------------------------------------------------------
// Label maps
// ---------------------------------------------------------------------------

const reasonLabels: Record<string, string> = {
  spam: 'Spam',
  inappropriate: 'Inappropriate Content',
  fraud: 'Fraud / Scam',
  duplicate: 'Duplicate Listing',
  wrong_category: 'Wrong Category',
  misleading: 'Misleading Info',
  other: 'Other',
};

function StatusBadge({ status }: { status: ReportStatus }) {
  switch (status) {
    case 'pending':
      return (
        <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400 text-xs gap-1">
          <Clock className="w-3 h-3" /> Pending
        </Badge>
      );
    case 'reviewed':
      return (
        <Badge className="bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-400 text-xs gap-1">
          <Eye className="w-3 h-3" /> Reviewed
        </Badge>
      );
    case 'resolved':
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 text-xs gap-1">
          <CheckCircle2 className="w-3 h-3" /> Resolved
        </Badge>
      );
    case 'dismissed':
      return (
        <Badge variant="secondary" className="text-xs gap-1">
          <XCircle className="w-3 h-3" /> Dismissed
        </Badge>
      );
  }
}

function reasonColor(reason: string) {
  switch (reason) {
    case 'fraud':
      return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
    case 'inappropriate':
      return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400';
    case 'spam':
      return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400';
    default:
      return 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400';
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AdminReportsPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const [reports, setReports] = useState<Report[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [page, setPage] = useState(1);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogAction, setDialogAction] = useState<'resolve' | 'dismiss'>('resolve');
  const [dialogReport, setDialogReport] = useState<Report | null>(null);
  const [adminNotes, setAdminNotes] = useState('');

  // ── Data fetching ──────────────────────────────────────────────────────
  const fetchReports = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Record<string, string | number> = { page, limit: PAGE_SIZE };
      if (statusFilter !== 'all') params.status = statusFilter;

      const res: PaginatedResponse<Report> = await api.trust.reports(params);
      setReports(res.results);
      setTotalCount(res.count);
    } catch {
      toast.error('Failed to load reports.');
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      router.push(routes.home());
      return;
    }
    fetchReports();
  }, [isAuthenticated, user, router, fetchReports]);

  // ── Dialog helpers ─────────────────────────────────────────────────────
  const openDialog = (report: Report, action: 'resolve' | 'dismiss') => {
    setDialogReport(report);
    setDialogAction(action);
    setAdminNotes('');
    setDialogOpen(true);
  };

  const handleSubmit = async () => {
    if (!dialogReport) return;
    setActionLoading(dialogReport.id);
    try {
      if (dialogAction === 'resolve') {
        await api.trust.resolveReport(dialogReport.id, { admin_notes: adminNotes });
        toast.success('Report resolved successfully.');
      } else {
        await api.trust.dismissReport(dialogReport.id, { admin_notes: adminNotes });
        toast.success('Report dismissed successfully.');
      }
      setDialogOpen(false);
      setDialogReport(null);
      fetchReports();
    } catch {
      toast.error('Failed to process report.');
    } finally {
      setActionLoading(null);
    }
  };

  // ── Data helpers ───────────────────────────────────────────────────────
  const getReporterName = (reporter: Report['reporter']) => {
    if (typeof reporter === 'object' && reporter !== null) {
      return reporter.username || `User #${reporter.id}`;
    }
    return `User #${reporter}`;
  };

  const getListingTitle = (listing: Report['listing']) => {
    if (typeof listing === 'object' && listing !== null) {
      return (listing as Record<string, string>).title || `Listing #${(listing as Record<string, number>).id}`;
    }
    return `Listing #${listing}`;
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
              <Shield className="w-7 h-7 text-emerald-600" />
              Reports & Moderation
            </h1>
            <p className="text-muted-foreground mt-1">
              Review and manage abuse reports from users
            </p>
          </div>
          <Button
            variant="outline"
            className="gap-2 shrink-0"
            onClick={() => router.push(routes.adminDashboard())}
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
                  <CardTitle className="text-lg">Reports ({totalCount})</CardTitle>
                  <CardDescription className="mt-0.5">Review and handle user-submitted reports</CardDescription>
                </div>
                <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 text-xs px-2.5 py-0.5">
                  {statusFilter === 'pending' ? 'Needs Review' : statusFilter.charAt(0).toUpperCase() + statusFilter.slice(1)}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <Tabs value={statusFilter} onValueChange={(val) => { setStatusFilter(val); setPage(1); }}>
                <TabsList className="mb-4">
                  <TabsTrigger value="pending" className="gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    Pending
                  </TabsTrigger>
                  <TabsTrigger value="resolved" className="gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Resolved
                  </TabsTrigger>
                  <TabsTrigger value="dismissed" className="gap-1.5">
                    <XCircle className="w-3.5 h-3.5" />
                    Dismissed
                  </TabsTrigger>
                  <TabsTrigger value="all">All</TabsTrigger>
                </TabsList>

                <TabsContent value={statusFilter}>
                  {isLoading ? (
                    <div className="space-y-4">
                      {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-32 w-full" />
                      ))}
                    </div>
                  ) : reports.length === 0 ? (
                    <div className="text-center py-16">
                      <Shield className="w-12 h-12 mx-auto mb-3 text-muted-foreground/30" />
                      <h3 className="font-semibold text-foreground text-lg mb-1">
                        No {statusFilter !== 'all' ? statusFilter : ''} reports
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        {statusFilter === 'pending'
                          ? 'No pending reports at the moment.'
                          : 'No reports found.'}
                      </p>
                    </div>
                  ) : (
                    <>
                      {/* ── Report Cards ─────────────────────────────────── */}
                      <div className="space-y-4 max-h-[700px] overflow-y-auto pr-1">
                        {reports.map((report) => (
                          <motion.div
                            key={report.id}
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.2 }}
                            className="border rounded-xl p-4 sm:p-5 space-y-3"
                          >
                            {/* Header row */}
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex items-start gap-3 min-w-0">
                                <div className="w-9 h-9 rounded-full bg-red-50 dark:bg-red-950/30 flex items-center justify-center shrink-0">
                                  <Flag className="w-4 h-4 text-red-600 dark:text-red-400" />
                                </div>
                                <div className="min-w-0">
                                  <p className="text-sm font-medium truncate">
                                    {getListingTitle(report.listing)}
                                  </p>
                                  <p className="text-xs text-muted-foreground">
                                    Reported by {getReporterName(report.reporter)}
                                  </p>
                                </div>
                              </div>
                              <StatusBadge status={report.status} />
                            </div>

                            {/* Reason + Date */}
                            <div className="flex items-center gap-2 flex-wrap">
                              <Badge
                                variant="secondary"
                                className={`text-xs capitalize ${reasonColor(report.reason)}`}
                              >
                                {reasonLabels[report.reason] || report.reason}
                              </Badge>
                              <span className="text-[10px] text-muted-foreground">
                                {getRelativeTime(report.created_at)}
                              </span>
                            </div>

                            {/* Description */}
                            {report.description && (
                              <p className="text-sm text-muted-foreground leading-relaxed bg-muted/50 rounded-md p-3">
                                &ldquo;{report.description}&rdquo;
                              </p>
                            )}

                            {/* Admin notes (already resolved / dismissed) */}
                            {report.admin_notes && report.status !== 'pending' && (
                              <div className="bg-emerald-50 dark:bg-emerald-950/20 rounded-md p-3 border border-emerald-100 dark:border-emerald-900/30">
                                <p className="text-[10px] font-medium text-emerald-700 dark:text-emerald-400 uppercase tracking-wide mb-1">
                                  Admin Notes
                                </p>
                                <p className="text-xs text-muted-foreground">{report.admin_notes}</p>
                              </div>
                            )}

                            {/* Action buttons */}
                            {report.status === 'pending' && (
                              <div className="flex items-center gap-2 pt-1">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="h-8 text-xs gap-1.5 flex-1 text-green-600 hover:text-green-700 hover:border-green-300 hover:bg-green-50 dark:hover:bg-green-950/30"
                                  onClick={() => openDialog(report, 'resolve')}
                                  disabled={actionLoading === report.id}
                                >
                                  {actionLoading === report.id ? (
                                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                  ) : (
                                    <CheckCircle2 className="w-3.5 h-3.5" />
                                  )}
                                  Resolve
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="h-8 text-xs gap-1.5 flex-1 hover:border-gray-400 hover:bg-gray-50 dark:hover:bg-gray-900/30"
                                  onClick={() => openDialog(report, 'dismiss')}
                                  disabled={actionLoading === report.id}
                                >
                                  {actionLoading === report.id ? (
                                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                  ) : (
                                    <XCircle className="w-3.5 h-3.5" />
                                  )}
                                  Dismiss
                                </Button>
                              </div>
                            )}
                          </motion.div>
                        ))}
                      </div>

                      {/* ── Pagination ────────────────────────────────────── */}
                      {totalPages > 1 && (
                        <div className="flex items-center justify-between mt-4 pt-4 border-t">
                          <p className="text-sm text-muted-foreground">
                            Page {page} of {totalPages} &middot; {totalCount} reports
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

      {/* ── Admin Notes Dialog ──────────────────────────────────────────── */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {dialogAction === 'resolve' ? (
                <>
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                  Resolve Report
                </>
              ) : (
                <>
                  <XCircle className="w-5 h-5 text-gray-500" />
                  Dismiss Report
                </>
              )}
            </DialogTitle>
            <DialogDescription>
              {dialogAction === 'resolve'
                ? 'Add admin notes to resolve this report. The reporter will be notified.'
                : 'Add admin notes explaining why this report is being dismissed.'}
            </DialogDescription>
          </DialogHeader>

          {dialogReport && (
            <div className="space-y-4">
              {/* Report summary */}
              <div className="bg-muted/50 rounded-md p-3 space-y-1.5">
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">Listing:</span>{' '}
                  {getListingTitle(dialogReport.listing)}
                </p>
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">Reporter:</span>{' '}
                  {getReporterName(dialogReport.reporter)}
                </p>
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">Reason:</span>{' '}
                  <Badge variant="secondary" className={`text-xs capitalize ml-1 ${reasonColor(dialogReport.reason)}`}>
                    {reasonLabels[dialogReport.reason] || dialogReport.reason}
                  </Badge>
                </p>
                {dialogReport.description && (
                  <p className="text-xs text-muted-foreground mt-1">
                    <span className="font-medium text-foreground">Description:</span>{' '}
                    {dialogReport.description}
                  </p>
                )}
              </div>

              {/* Admin notes textarea */}
              <div className="space-y-2">
                <label htmlFor="admin-notes" className="text-sm font-medium">
                  Admin Notes
                </label>
                <Textarea
                  id="admin-notes"
                  placeholder="Describe your action and any relevant details..."
                  value={adminNotes}
                  onChange={(e) => setAdminNotes(e.target.value)}
                  rows={4}
                  className="resize-none"
                />
              </div>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={actionLoading !== null}
              className={
                dialogAction === 'resolve'
                  ? 'bg-green-600 hover:bg-green-700 text-white'
                  : 'bg-gray-600 hover:bg-gray-700 text-white'
              }
            >
              {actionLoading !== null ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : dialogAction === 'resolve' ? (
                <CheckCircle2 className="w-4 h-4 mr-2" />
              ) : (
                <XCircle className="w-4 h-4 mr-2" />
              )}
              {dialogAction === 'resolve' ? 'Resolve' : 'Dismiss'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
