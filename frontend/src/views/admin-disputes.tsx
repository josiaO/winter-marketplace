'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertTriangle,
  ArrowUpRight,
  Loader2,
  RefreshCcw,
  DollarSign,
  Shield,
  Eye,
  Image,
  Video,
  FileText,
  Clock,
  CheckCircle2,
  XCircle,
  Search,
  MessageSquare,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, formatDate, getRelativeTime, getInitials } from '@/lib/helpers';
import type { Order, DisputeStatus, PaginatedResponse } from '@/types/api';

const PAGE_SIZE = 50;

const disputeReasonLabels: Record<string, string> = {
  item_not_received: 'Item Not Received',
  item_not_as_described: 'Item Not As Described',
  damaged_item: 'Damaged Item',
  wrong_item: 'Wrong Item',
  quality_issue: 'Quality Issue',
  seller_unresponsive: 'Seller Unresponsive',
  payment_issue: 'Payment Issue',
  other: 'Other',
};

const disputeStatusConfig: Record<DisputeStatus, { label: string; color: string; icon: typeof AlertTriangle }> = {
  open: {
    label: 'Open',
    color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    icon: AlertTriangle,
  },
  under_review: {
    label: 'Under Review',
    color: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
    icon: Search,
  },
  resolved: {
    label: 'Resolved',
    color: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
    icon: CheckCircle2,
  },
  dismissed: {
    label: 'Dismissed',
    color: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
    icon: XCircle,
  },
};

function DisputeStatusBadge({ status }: { status: DisputeStatus }) {
  const config = disputeStatusConfig[status] || disputeStatusConfig.open;
  const Icon = config.icon;
  return (
    <Badge variant="secondary" className={`text-xs gap-1 ${config.color}`}>
      <Icon className="w-3 h-3" />
      {config.label}
    </Badge>
  );
}

function DisputeCard({
  order,
  onResolve,
  isLoading,
}: {
  order: Order;
  onResolve: (order: Order) => void;
  isLoading: boolean;
}) {
  const dispute = order.dispute;
  if (!dispute) return null;

  const buyerName =
    typeof order.buyer === 'object' ? order.buyer.username : `User #${order.buyer}`;
  const sellerName =
    typeof order.seller === 'object' ? order.seller.username : `Seller #${order.seller}`;
  const buyerAvatar =
    typeof order.buyer === 'object' ? order.buyer.avatar : undefined;
  const sellerAvatar =
    typeof order.seller === 'object' ? order.seller.avatar : undefined;
  const buyerInitials =
    typeof order.buyer === 'object'
      ? getInitials(`${order.buyer.first_name} ${order.buyer.last_name}`)
      : '?';
  const sellerInitials =
    typeof order.seller === 'object'
      ? getInitials(`${order.seller.first_name} ${order.seller.last_name}`)
      : '?';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.2 }}
    >
      <Card className="border shadow-sm hover:shadow-md transition-shadow">
        <CardContent className="p-4 sm:p-5 space-y-4">
          {/* Header row */}
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-100 dark:bg-red-900/30 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400" />
              </div>
              <div>
                <p className="font-mono text-sm font-medium">
                  #{order.order_number?.slice(-8) || order.id}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {getRelativeTime(dispute.created_at)}
                </p>
              </div>
            </div>
            <DisputeStatusBadge status={dispute.status} />
          </div>

          {/* Parties */}
          <div className="grid grid-cols-2 gap-4">
            <div className="flex items-center gap-2">
              <Avatar className="h-7 w-7">
                <AvatarImage src={buyerAvatar} />
                <AvatarFallback className="text-[10px]">{buyerInitials}</AvatarFallback>
              </Avatar>
              <div className="min-w-0">
                <p className="text-[10px] text-muted-foreground uppercase">Buyer</p>
                <p className="text-sm font-medium truncate">{buyerName}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Avatar className="h-7 w-7">
                <AvatarImage src={sellerAvatar} />
                <AvatarFallback className="text-[10px]">{sellerInitials}</AvatarFallback>
              </Avatar>
              <div className="min-w-0">
                <p className="text-[10px] text-muted-foreground uppercase">Seller</p>
                <p className="text-sm font-medium truncate">{sellerName}</p>
              </div>
            </div>
          </div>

          <Separator />

          {/* Details */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
            <div>
              <p className="text-[10px] text-muted-foreground uppercase mb-0.5">Reason</p>
              <Badge variant="secondary" className="text-xs">
                {disputeReasonLabels[dispute.reason] || dispute.reason}
              </Badge>
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground uppercase mb-0.5">Amount</p>
              <p className="font-semibold">{formatTZS(order.total)}</p>
            </div>
            <div>
              <p className="text-[10px] text-muted-foreground uppercase mb-0.5">Items</p>
              <p className="text-muted-foreground">
                {order.items.length} item{order.items.length !== 1 ? 's' : ''}
              </p>
            </div>
          </div>

          {/* Evidence */}
          {(dispute.evidence_images && dispute.evidence_images.length > 0) ||
          dispute.evidence_video ? (
            <div>
              <p className="text-[10px] text-muted-foreground uppercase mb-2">Evidence</p>
              <div className="flex flex-wrap gap-2">
                {dispute.evidence_images &&
                  dispute.evidence_images.length > 0 &&
                  dispute.evidence_images.slice(0, 4).map((img, i) => (
                    <a
                      key={i}
                      href={img}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="relative w-14 h-14 rounded-lg bg-muted overflow-hidden border hover:border-emerald-500 transition-colors group"
                    >
                      <img
                        src={img}
                        alt={`Evidence ${i + 1}`}
                        className="w-full h-full object-cover"
                      />
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                        <Eye className="w-4 h-4 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                    </a>
                  ))}
                {dispute.evidence_video && (
                  <a
                    href={dispute.evidence_video}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-14 h-14 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors"
                  >
                    <Video className="w-5 h-5 text-red-600 dark:text-red-400" />
                  </a>
                )}
              </div>
            </div>
          ) : null}

          {/* Admin notes & resolution */}
          {dispute.resolution && (
            <div className="bg-emerald-50 dark:bg-emerald-900/10 rounded-lg p-3 text-sm">
              <p className="font-medium text-emerald-800 dark:text-emerald-400 mb-1">Resolution</p>
              <p className="text-emerald-700 dark:text-emerald-300">{dispute.resolution}</p>
            </div>
          )}
          {dispute.admin_notes && (
            <div className="bg-muted/50 rounded-lg p-3 text-sm">
              <p className="font-medium text-muted-foreground mb-1 flex items-center gap-1.5">
                <MessageSquare className="w-3.5 h-3.5" />
                Admin Notes
              </p>
              <p>{dispute.admin_notes}</p>
            </div>
          )}

          {/* Actions */}
          {dispute.status === 'open' || dispute.status === 'under_review' ? (
            <div className="flex items-center gap-2 pt-1">
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1.5 flex-1 border-emerald-200 text-emerald-700 hover:bg-emerald-50 dark:border-emerald-800 dark:text-emerald-400 dark:hover:bg-emerald-900/20"
                onClick={() => onResolve(order)}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Shield className="w-3.5 h-3.5" />
                )}
                Resolve Dispute
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs gap-1.5 flex-1 text-red-600 hover:text-red-700 border-red-200 hover:bg-red-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/20"
                onClick={() =>
                  onResolve({
                    ...order,
                    dispute: { ...order.dispute!, status: 'open' },
                  })
                }
                disabled={isLoading}
              >
                <RefreshCcw className="w-3.5 h-3.5" />
                Refund Buyer
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </motion.div>
  );
}

export function AdminDisputesPage() {
  const { navigate } = useUIStore();
  const { user, isAuthenticated } = useAuthStore();
  const [allOrders, setAllOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<string>('open');
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogOrder, setDialogOrder] = useState<Order | null>(null);
  const [resolutionAction, setResolutionAction] = useState<string>('release');
  const [adminNotes, setAdminNotes] = useState('');

  const fetchOrders = useCallback(async () => {
    setIsLoading(true);
    try {
      const res: PaginatedResponse<Order> = await api.commerce.orders({
        status: 'disputed',
        limit: PAGE_SIZE,
      });
      const disputed = res.results.filter((o) => o.dispute !== null);
      setAllOrders(disputed);
    } catch {
      toast.error('Failed to load disputed orders.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      navigate({ view: 'home' });
      return;
    }
    fetchOrders();
  }, [isAuthenticated, user, navigate, fetchOrders]);

  const filteredOrders = useMemo(() => {
    if (activeTab === 'all') return allOrders;
    return allOrders.filter((o) => o.dispute?.status === activeTab);
  }, [allOrders, activeTab]);

  const tabCounts = useMemo(() => ({
    open: allOrders.filter((o) => o.dispute?.status === 'open').length,
    under_review: allOrders.filter((o) => o.dispute?.status === 'under_review').length,
    resolved: allOrders.filter((o) => o.dispute?.status === 'resolved').length,
    dismissed: allOrders.filter((o) => o.dispute?.status === 'dismissed').length,
  }), [allOrders]);

  const openDialog = (order: Order, action: string = 'release') => {
    setDialogOrder(order);
    setResolutionAction(action);
    setAdminNotes('');
    setDialogOpen(true);
  };

  const handleResolveDispute = async () => {
    if (!dialogOrder) return;
    setActionLoading(dialogOrder.id);
    try {
      if (resolutionAction === 'refund') {
        await api.escrow.refundTransaction(dialogOrder.id, {
          reason: adminNotes || 'Dispute resolved with refund.',
        });
        toast.success('Refund initiated successfully.');
      } else {
        await api.escrow.releaseTransaction(dialogOrder.id);
        toast.success('Payment released to seller successfully.');
      }
      setDialogOpen(false);
      fetchOrders();
    } catch {
      toast.error('Failed to resolve dispute.');
    } finally {
      setActionLoading(null);
    }
  };

  if (!isAuthenticated || !user || user.role !== 'admin') return null;

  const totalDisputedAmount = filteredOrders.reduce((sum, o) => sum + o.total, 0);

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center gap-2">
              <AlertTriangle className="w-7 h-7 text-emerald-600" />
              Order Disputes
            </h1>
            <p className="text-muted-foreground mt-1">
              Review and resolve order disputes between buyers and sellers
            </p>
          </div>
          <Button
            variant="outline"
            className="gap-2 shrink-0"
            onClick={() => navigate({ view: 'admin-dashboard' })}
          >
            <ArrowUpRight className="w-4 h-4" />
            Back to Dashboard
          </Button>
        </motion.div>

        {/* Summary Stats */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="grid grid-cols-2 sm:grid-cols-4 gap-4"
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-100 dark:bg-red-900/30 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400" />
              </div>
              <div>
                <p className="text-2xl font-bold">{tabCounts.open}</p>
                <p className="text-xs text-muted-foreground">Open Disputes</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-md shadow-black/5">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center shrink-0">
                <DollarSign className="w-5 h-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <p className="text-2xl font-bold">{formatTZS(totalDisputedAmount)}</p>
                <p className="text-xs text-muted-foreground">Total Disputed Amount</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-md shadow-black/5">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center shrink-0">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
              </div>
              <div>
                <p className="text-2xl font-bold">{tabCounts.resolved}</p>
                <p className="text-xs text-muted-foreground">Resolved</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-0 shadow-md shadow-black/5">
            <CardContent className="p-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gray-100 dark:bg-gray-900/30 flex items-center justify-center shrink-0">
                <XCircle className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              </div>
              <div>
                <p className="text-2xl font-bold">{tabCounts.dismissed}</p>
                <p className="text-xs text-muted-foreground">Dismissed</p>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Tabs */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-0">
              <CardTitle className="text-lg">Dispute Management</CardTitle>
              <CardDescription>
                Filter and manage disputes by status
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="w-full sm:w-auto grid grid-cols-2 sm:grid-cols-4 mb-6">
                  <TabsTrigger value="open" className="gap-1.5 text-xs sm:text-sm">
                    <AlertTriangle className="w-3.5 h-3.5 hidden sm:block" />
                    Open
                    {tabCounts.open > 0 && (
                      <Badge variant="secondary" className="ml-1 h-5 min-w-5 px-1.5 text-[10px] bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                        {tabCounts.open}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="under_review" className="gap-1.5 text-xs sm:text-sm">
                    <Search className="w-3.5 h-3.5 hidden sm:block" />
                    Under Review
                    {tabCounts.under_review > 0 && (
                      <Badge variant="secondary" className="ml-1 h-5 min-w-5 px-1.5 text-[10px] bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                        {tabCounts.under_review}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="resolved" className="gap-1.5 text-xs sm:text-sm">
                    <CheckCircle2 className="w-3.5 h-3.5 hidden sm:block" />
                    Resolved
                    {tabCounts.resolved > 0 && (
                      <Badge variant="secondary" className="ml-1 h-5 min-w-5 px-1.5 text-[10px] bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                        {tabCounts.resolved}
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="dismissed" className="gap-1.5 text-xs sm:text-sm">
                    <XCircle className="w-3.5 h-3.5 hidden sm:block" />
                    Dismissed
                    {tabCounts.dismissed > 0 && (
                      <Badge variant="secondary" className="ml-1 h-5 min-w-5 px-1.5 text-[10px] bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400">
                        {tabCounts.dismissed}
                      </Badge>
                    )}
                  </TabsTrigger>
                </TabsList>

                {['open', 'under_review', 'resolved', 'dismissed'].map((tab) => (
                  <TabsContent key={tab} value={tab}>
                    {isLoading ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {Array.from({ length: 4 }).map((_, i) => (
                          <Skeleton key={i} className="h-72 w-full rounded-xl" />
                        ))}
                      </div>
                    ) : filteredOrders.length === 0 ? (
                      <div className="text-center py-16">
                        <AlertTriangle className="w-12 h-12 mx-auto mb-3 text-muted-foreground/30" />
                        <h3 className="font-semibold text-foreground text-lg mb-1">
                          No {tab.replace('_', ' ')} disputes
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          {tab === 'open'
                            ? 'All disputes have been addressed.'
                            : `No disputes with status "${tab.replace('_', ' ')}".`}
                        </p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <AnimatePresence mode="popLayout">
                          {filteredOrders.map((order) => (
                            <DisputeCard
                              key={order.id}
                              order={order}
                              onResolve={(o) => openDialog(o)}
                              isLoading={actionLoading === order.id}
                            />
                          ))}
                        </AnimatePresence>
                      </div>
                    )}
                  </TabsContent>
                ))}
              </Tabs>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Resolve Dispute Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-emerald-600" />
              Resolve Dispute
            </DialogTitle>
            <DialogDescription>
              Choose an action to resolve this dispute
            </DialogDescription>
          </DialogHeader>
          {dialogOrder && (
            <div className="space-y-4">
              {/* Order summary */}
              <div className="bg-muted/50 rounded-lg p-3 space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Order</span>
                  <span className="font-mono font-medium">
                    #{dialogOrder.order_number?.slice(-8) || dialogOrder.id}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Amount</span>
                  <span className="font-bold">{formatTZS(dialogOrder.total)}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Buyer</span>
                  <span>
                    {typeof dialogOrder.buyer === 'object'
                      ? dialogOrder.buyer.username
                      : `User #${dialogOrder.buyer}`}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Seller</span>
                  <span>
                    {typeof dialogOrder.seller === 'object'
                      ? dialogOrder.seller.username
                      : `Seller #${dialogOrder.seller}`}
                  </span>
                </div>
                {dialogOrder.dispute?.reason && (
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">Reason</span>
                    <span className="capitalize">
                      {disputeReasonLabels[dialogOrder.dispute.reason] ||
                        dialogOrder.dispute.reason}
                    </span>
                  </div>
                )}
              </div>

              {/* Resolution select */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Resolution Action</label>
                <Select value={resolutionAction} onValueChange={setResolutionAction}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select action" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="release">
                      <span className="flex items-center gap-2">
                        <DollarSign className="w-3.5 h-3.5 text-teal-600" />
                        Release Payment to Seller
                      </span>
                    </SelectItem>
                    <SelectItem value="refund">
                      <span className="flex items-center gap-2">
                        <RefreshCcw className="w-3.5 h-3.5 text-emerald-600" />
                        Refund Buyer
                      </span>
                    </SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  {resolutionAction === 'refund'
                    ? 'This will initiate a full refund to the buyer from escrow.'
                    : 'This will release the held payment to the seller from escrow.'}
                </p>
              </div>

              {/* Admin notes */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Admin Notes</label>
                <Textarea
                  placeholder="Add notes about this resolution..."
                  value={adminNotes}
                  onChange={(e) => setAdminNotes(e.target.value)}
                  rows={3}
                />
              </div>
            </div>
          )}
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleResolveDispute}
              disabled={actionLoading !== null || !resolutionAction}
              className={
                resolutionAction === 'refund'
                  ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                  : 'bg-teal-600 hover:bg-teal-700 text-white'
              }
            >
              {actionLoading !== null ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : resolutionAction === 'refund' ? (
                <RefreshCcw className="w-4 h-4 mr-2" />
              ) : (
                <DollarSign className="w-4 h-4 mr-2" />
              )}
              {resolutionAction === 'refund' ? 'Confirm Refund' : 'Confirm Release'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
