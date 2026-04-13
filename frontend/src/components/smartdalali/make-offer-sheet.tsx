'use client';

import { useState, useEffect } from 'react';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api-client';
import { formatTZS } from '@/lib/helpers';
import { toast } from 'sonner';
import { ApiClientError } from '@/types/api';
import { Loader2 } from 'lucide-react';

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  listingId: number;
  listedPrice: number;
};

export function MakeOfferSheet({ open, onOpenChange, listingId, listedPrice }: Props) {
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [activeCount, setActiveCount] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setAmount('');
    setNote('');
    api.commerce
      .offersActiveCount()
      .then((r) => setActiveCount(r.active_count))
      .catch(() => setActiveCount(null));
  }, [open]);

  const min = listedPrice * 0.5;
  const max = listedPrice * 0.99;
  const numAmount = Number(String(amount).replace(/,/g, ''));
  const invalidRange =
    amount !== '' && (Number.isNaN(numAmount) || numAmount < min || numAmount > max);

  const submit = async () => {
    if (activeCount != null && activeCount >= 3) {
      toast.error('You can have at most 3 active offers at a time.');
      return;
    }
    if (Number.isNaN(numAmount) || numAmount < min) {
      toast.error('Offer must be at least 50% of the listed price.');
      return;
    }
    if (numAmount > max) {
      toast.error('Offer must be at most 99% of the listed price.');
      return;
    }
    setSubmitting(true);
    try {
      await api.commerce.offersCreate({
        listing_id: listingId,
        amount: numAmount,
        note: note.trim() || undefined,
      });
      toast.success('Offer sent! The seller will be notified.');
      onOpenChange(false);
    } catch (e) {
      const msg =
        e instanceof ApiClientError ? e.detail || e.message : 'Could not send offer';
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="rounded-t-2xl max-h-[90vh] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Make an offer</SheetTitle>
          <SheetDescription>
            Negotiate securely on SmartDalali. Your offer stays between you and the seller.
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-4 px-4 pb-2">
          <div>
            <p className="text-sm text-muted-foreground">Listed price</p>
            <p className="text-xl font-bold text-foreground">{formatTZS(listedPrice)}</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="offer-amt">Your offer (TZS)</Label>
            <Input
              id="offer-amt"
              inputMode="decimal"
              placeholder="e.g. 70000"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
            {invalidRange && (
              <p className="text-xs text-destructive">
                Offer must be between 50% and 99% of the listed price ({formatTZS(Math.round(min))} –{' '}
                {formatTZS(Math.round(max))}).
              </p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="offer-note">Note to seller (optional)</Label>
            <Textarea
              id="offer-note"
              placeholder="e.g. I am buying 2 pairs, can you do a discount?"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
            />
          </div>
          {activeCount != null && (
            <p className="text-xs text-muted-foreground">Active offers: {activeCount} / 3</p>
          )}
        </div>
        <SheetFooter className="gap-2 sm:flex-col">
          <Button className="w-full rounded-xl" disabled={submitting || invalidRange || !amount} onClick={() => void submit()}>
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Send offer'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
