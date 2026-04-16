'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Link as LinkIcon,
  Plus,
  Copy,
  CheckCircle2,
  Clock,
  XCircle,
  MoreVertical,
  ArrowUpRight,
  DollarSign,
  Loader2,
  ExternalLink,
  ShieldCheck,
  Search,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, formatDate } from '@/lib/helpers';
import type { PayLink, CreatePayLinkPayload, Listing } from '@/types/api';

export function SellerPayLinksPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const [payLinks, setPayLinks] = useState<PayLink[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  // Form state
  const [selectedListing, setSelectedListing] = useState<Listing | null>(null);
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [listings, setListings] = useState<Listing[]>([]);
  const [isLoadingListings, setIsLoadingListings] = useState(false);

  // ── Data fetching ──────────────────────────────────────────────────────
  const fetchPayLinks = useCallback(async () => {
    setIsLoading(true);
    try {
      // Backend doesn't have a direct "list my pay links" yet in API client, 
      // but escrow object exists. For now we assume a list endpoint exists or handle error.
      // Actually escrow.transactions is there. For PayLinks we might need to add it.
      // Since it's a new feature, we'll try to fetch if available.
      // For now, we simulate an empty list if not implemented to avoid crash.
      setPayLinks([]);
    } catch {
      toast.error('Failed to load payment links.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchListings = useCallback(async () => {
    setIsLoadingListings(true);
    try {
      const res = await api.listings.sellerListings();
      setListings(res.results);
    } catch {
      toast.error('Failed to load your listings.');
    } finally {
      setIsLoadingListings(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'seller') {
      router.push(routes.home());
      return;
    }
    fetchPayLinks();
    fetchListings();
  }, [isAuthenticated, user, router, fetchPayLinks, fetchListings]);

  const handleCreatePayLink = async () => {
    if (!selectedListing && !amount) {
      toast.error('Please select a listing or enter an amount.');
      return;
    }
    setIsCreating(true);
    try {
      const payload: CreatePayLinkPayload = {
        listing_id: selectedListing?.id,
        amount: amount ? Number(amount) : undefined,
        description: description || undefined,
      };
      const res = await api.escrow.createPayLink(payload);
      toast.success('Payment link created successfully!');
      setPayLinks([res, ...payLinks]);
      setShowCreateDialog(false);
      // Reset form
      setSelectedListing(null);
      setAmount('');
      setDescription('');
    } catch (err: any) {
      toast.error(err.message || 'Failed to create payment link.');
    } finally {
      setIsCreating(false);
    }
  };

  const copyToClipboard = (token: string) => {
    const url = `${window.location.origin}/pay/${token}`;
    navigator.clipboard.writeText(url);
    toast.success('Link copied to clipboard!');
  };

  // ── Guard ──────────────────────────────────────────────────────────────
  if (!isAuthenticated || !user || user.role !== 'seller') return null;

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
              <LinkIcon className="w-7 h-7 text-emerald-600" />
              Secure Payment Links
            </h1>
            <p className="text-muted-foreground mt-1">
              Create ad-hoc escrow links for off-platform or custom deals
            </p>
          </div>
          <Button
            className="gap-2 shrink-0 bg-emerald-600 hover:bg-emerald-700"
            onClick={() => setShowCreateDialog(true)}
          >
            <Plus className="w-4 h-4" />
            Create Link
          </Button>
        </motion.div>

        {/* Info Card */}
        <motion.div
           initial={{ opacity: 0, scale: 0.98 }}
           animate={{ opacity: 1, scale: 1 }}
           transition={{ delay: 0.1 }}
        >
          <Card className="bg-emerald-50/50 dark:bg-emerald-950/20 border-emerald-100 dark:border-emerald-900/50">
            <CardContent className="p-4 flex gap-4">
              <div className="w-10 h-10 rounded-full bg-emerald-100 dark:bg-emerald-900/50 flex items-center justify-center shrink-0">
                <ShieldCheck className="w-5 h-5 text-emerald-600" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-semibold text-emerald-900 dark:text-emerald-400">Escrow Protected</p>
                <p className="text-xs text-emerald-800/70 dark:text-emerald-400/70 leading-relaxed">
                  Every link you share uses SmartDalali's secure escrow. The buyer pays SmarDalali, 
                  you fulfill the order, and funds are released only after confirmation or the trust window expires.
                </p>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Links Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-3 px-4 sm:px-6">
              <CardTitle className="text-lg">Your Active Links</CardTitle>
            </CardHeader>
            <CardContent className="px-0 sm:px-6">
              {isLoading ? (
                <div className="p-6 space-y-4">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <Skeleton key={i} className="h-12 w-full" />
                  ))}
                </div>
              ) : payLinks.length === 0 ? (
                <div className="text-center py-16">
                  <LinkIcon className="w-12 h-12 mx-auto mb-3 text-muted-foreground/30" />
                  <h3 className="font-semibold text-foreground text-lg mb-1">
                    No payment links yet
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Click "Create Link" to generate your first secure payment QR or link.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/30">
                        <TableHead className="w-[100px]">Link ID</TableHead>
                        <TableHead>Listing / Description</TableHead>
                        <TableHead>Amount</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {payLinks.map((link) => (
                        <TableRow key={link.id}>
                          <TableCell className="font-mono text-xs">#{link.id}</TableCell>
                          <TableCell>
                            <div className="min-w-[150px]">
                              <p className="text-sm font-medium">
                                {link.listing_title || link.description || 'Custom Link'}
                              </p>
                              <p className="text-[10px] text-muted-foreground">
                                Created {formatDate(link.created_at)}
                              </p>
                            </div>
                          </TableCell>
                          <TableCell className="font-semibold text-emerald-600">
                             {formatTZS(link.amount)}
                          </TableCell>
                          <TableCell>
                             <Badge variant="secondary" className="capitalize text-[10px] bg-emerald-50 text-emerald-700">
                               {link.is_active ? 'Active' : 'Completed'}
                             </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                             <div className="flex items-center justify-end gap-2">
                               <Button variant="outline" size="sm" className="h-8 gap-1" onClick={() => copyToClipboard(link.token)}>
                                 <Copy className="w-3.5 h-3.5" />
                                 Copy
                               </Button>
                               <Button variant="ghost" size="icon" className="h-8 w-8">
                                 <MoreVertical className="w-3.5 h-3.5" />
                               </Button>
                             </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Create Payment Link</DialogTitle>
            <DialogDescription>
              Generate a unique URL for a specific listing or a custom amount.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Select Listing (Optional)</label>
              <select 
                className="w-full h-10 rounded-md border bg-background px-3 text-sm"
                value={selectedListing?.id || ''}
                onChange={(e) => {
                   const id = Number(e.target.value);
                   const l = listings.find(listing => listing.id === id) || null;
                   setSelectedListing(l);
                   if (l) setAmount(String(l.price));
                }}
              >
                <option value="">No specific listing</option>
                {listings.map(l => (
                  <option key={l.id} value={l.id}>{l.title} ({formatTZS(l.price)})</option>
                ))}
              </select>
            </div>
            
            <div className="space-y-2">
              <label className="text-sm font-medium">Amount (TZS)</label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <input
                  type="number"
                  className="w-full h-10 rounded-md border bg-background pl-9 pr-3 text-sm"
                  placeholder="0.00"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Description</label>
              <textarea
                className="w-full min-h-[80px] rounded-md border bg-background p-3 text-sm resize-none"
                placeholder="What is this payment for?"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>Cancel</Button>
            <Button 
                className="bg-emerald-600 hover:bg-emerald-700" 
                onClick={handleCreatePayLink}
                disabled={isCreating}
            >
              {isCreating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
              Generate Link
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
