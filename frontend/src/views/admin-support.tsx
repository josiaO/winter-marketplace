'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  LifeBuoy,
  MessageSquare,
  Clock,
  CheckCircle2,
  XCircle,
  MoreVertical,
  ArrowUpRight,
  Filter,
  Loader2,
  ChevronLeft,
  ChevronRight,
  User,
  ExternalLink,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatDate, getRelativeTime } from '@/lib/helpers';
import type { SupportRequest, SupportRequestStatus, PaginatedResponse } from '@/types/api';

const PAGE_SIZE = 20;

export function AdminSupportPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const [requests, setRequests] = useState<SupportRequest[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('pending');
  const [page, setPage] = useState(1);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  // ── Data fetching ──────────────────────────────────────────────────────
  const fetchRequests = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Record<string, string | number> = { page, limit: PAGE_SIZE };
      if (activeTab !== 'all') params.status = activeTab;

      const res: PaginatedResponse<SupportRequest> = await api.communications.supportRequests(params);
      setRequests(res.results);
      setTotalCount(res.count);
    } catch {
      toast.error('Failed to load support requests.');
    } finally {
      setIsLoading(false);
    }
  }, [activeTab, page]);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      router.push(routes.home());
      return;
    }
    fetchRequests();
  }, [isAuthenticated, user, router, fetchRequests]);

  const handleUpdateStatus = async (id: number, status: SupportRequestStatus) => {
    setActionLoading(id);
    try {
      await api.communications.updateSupportRequest(id, { status });
      toast.success(`Support request status updated to ${status}.`);
      fetchRequests();
    } catch {
      toast.error('Failed to update status.');
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
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center gap-2">
              <LifeBuoy className="w-7 h-7 text-emerald-600" />
              Support Requests
            </h1>
            <p className="text-muted-foreground mt-1">
              Manage platform-wide user support and inquiries
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

        {/* Filters + Stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg">Ticket Queue</CardTitle>
                  <CardDescription>{totalCount} total request(s)</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Tabs value={activeTab} onValueChange={(val) => { setActiveTab(val); setPage(1); }}>
                <TabsList className="mb-4">
                  <TabsTrigger value="pending" className="gap-1.5">
                    <Clock className="w-3.5 h-3.5" />
                    Pending
                  </TabsTrigger>
                  <TabsTrigger value="in_progress" className="gap-1.5">
                    <Filter className="w-3.5 h-3.5" />
                    In Progress
                  </TabsTrigger>
                  <TabsTrigger value="resolved" className="gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Resolved
                  </TabsTrigger>
                  <TabsTrigger value="all">All</TabsTrigger>
                </TabsList>

                <TabsContent value={activeTab} className="space-y-4">
                  {isLoading ? (
                    <div className="space-y-4">
                      {Array.from({ length: 4 }).map((_, i) => (
                        <Skeleton key={i} className="h-32 w-full rounded-xl" />
                      ))}
                    </div>
                  ) : requests.length === 0 ? (
                    <div className="text-center py-16">
                      <MessageSquare className="w-12 h-12 mx-auto mb-3 text-muted-foreground/30" />
                      <h3 className="font-semibold text-foreground text-lg mb-1">
                        No {activeTab !== 'all' ? activeTab : ''} requests
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        All users seem to be happy at the moment.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {requests.map((req) => (
                        <motion.div
                          key={req.id}
                          layout
                          initial={{ opacity: 0, scale: 0.98 }}
                          animate={{ opacity: 1, scale: 1 }}
                          className="group border rounded-xl overflow-hidden bg-card hover:border-emerald-200 transition-all shadow-sm"
                        >
                          <div className="p-4 sm:p-5 flex flex-col sm:flex-row gap-4">
                            <div className="flex-1 min-w-0 space-y-2">
                              <div className="flex items-center gap-2 flex-wrap">
                                <Badge
                                  className={`capitalize text-[10px] ${
                                    req.status === 'pending'
                                      ? 'bg-yellow-100 text-yellow-800'
                                      : req.status === 'in_progress'
                                      ? 'bg-blue-100 text-blue-800'
                                      : 'bg-green-100 text-green-800'
                                  }`}
                                  variant="secondary"
                                >
                                  {req.status.replace('_', ' ')}
                                </Badge>
                                <span className="text-xs text-muted-foreground">
                                  #{req.id} • Submitted {getRelativeTime(req.created_at)}
                                </span>
                              </div>
                              <h3 className="text-base font-bold text-foreground">
                                {req.subject}
                              </h3>
                              <p className="text-sm text-muted-foreground leading-relaxed line-clamp-2">
                                {req.message}
                              </p>
                              
                              <div className="flex items-center gap-3 pt-2">
                                <Avatar className="h-6 w-6">
                                  <AvatarFallback className="text-[10px] bg-emerald-50 text-emerald-600">
                                    <User className="w-3 h-3" />
                                  </AvatarFallback>
                                </Avatar>
                                <span className="text-xs text-muted-foreground font-medium">
                                  User ID: #{req.user}
                                </span>
                              </div>
                            </div>

                            <div className="flex flex-row sm:flex-col items-center justify-end gap-2 shrink-0">
                               {req.status === 'pending' && (
                                 <Button 
                                   size="sm" 
                                   variant="secondary" 
                                   className="text-xs h-8"
                                   disabled={actionLoading === req.id}
                                   onClick={() => handleUpdateStatus(req.id, 'in_progress')}
                                 >
                                    Claim
                                 </Button>
                               )}
                               {req.status !== 'resolved' && req.status !== 'closed' && (
                                 <Button 
                                   size="sm" 
                                   variant="outline" 
                                   className="text-xs h-8 border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                                   disabled={actionLoading === req.id}
                                   onClick={() => handleUpdateStatus(req.id, 'resolved')}
                                 >
                                    Mark Resolved
                                 </Button>
                               )}
                               <DropdownMenu>
                                 <DropdownMenuTrigger asChild>
                                   <Button variant="ghost" size="icon" className="h-8 w-8">
                                     <MoreVertical className="w-4 h-4" />
                                   </Button>
                                 </DropdownMenuTrigger>
                                 <DropdownMenuContent align="end">
                                   <DropdownMenuItem onClick={() => handleUpdateStatus(req.id, 'closed')} className="text-red-600">
                                     Close Ticket
                                   </DropdownMenuItem>
                                   <DropdownMenuItem onClick={() => router.push(routes.messages())}>
                                     Message User
                                   </DropdownMenuItem>
                                 </DropdownMenuContent>
                               </DropdownMenu>
                            </div>
                          </div>
                        </motion.div>
                      ))}

                      {/* Pagination */}
                      {totalPages > 1 && (
                        <div className="flex items-center justify-between mt-4 pt-4 border-t">
                          <p className="text-sm text-muted-foreground">
                            Page {page} of {totalPages}
                          </p>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={page <= 1}
                              onClick={() => setPage((p) => p - 1)}
                            >
                              <ChevronLeft className="w-4 h-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={page >= totalPages}
                              onClick={() => setPage((p) => p + 1)}
                            >
                              <ChevronRight className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>
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
