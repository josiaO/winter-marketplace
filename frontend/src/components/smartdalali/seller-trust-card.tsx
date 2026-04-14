'use client';

import { Shield, ShieldCheck, Star } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { getInitials, getRelativeTime } from '@/lib/helpers';
import { cn } from '@/lib/utils';
import type { SellerTrustBlock } from '@/types/api';
import Image from 'next/image';

function completionBarClass(tier: string) {
  if (tier === 'high') return 'bg-emerald-500';
  if (tier === 'mid') return 'bg-amber-500';
  if (tier === 'low') return 'bg-red-500';
  return 'bg-muted-foreground/40';
}

export function SellerTrustCard({
  trust,
  reviewsTotal,
  onSeeAllReviews,
}: {
  trust: SellerTrustBlock | null | undefined;
  reviewsTotal?: number;
  onSeeAllReviews?: () => void;
}) {
  if (!trust || !trust.seller_name) return null;

  const pct = trust.completion_rate_pct;
  const barWidth = pct != null ? Math.min(100, Math.max(0, pct)) : 0;

  return (
    <div className="rounded-xl border bg-card p-4 space-y-3">
      <div className="flex items-start gap-3">
        <Avatar className="h-11 w-11">
          <AvatarFallback className="text-xs font-semibold bg-primary/10 text-primary">
            {getInitials(trust.seller_name)}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-semibold text-foreground truncate">{trust.seller_name}</span>
            {trust.seller_verified_badge && (
              <Badge variant="secondary" className="text-[10px] h-5 px-1.5 bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200">
                Verified
              </Badge>
            )}
          </div>
          {trust.store_name && (
            <p className="text-xs text-muted-foreground truncate">{trust.store_name}</p>
          )}
        </div>
      </div>

      {pct != null && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-muted-foreground">Completion rate</span>
            <span className="font-medium tabular-nums text-emerald-600 dark:text-emerald-400">{pct}%</span>
          </div>
          <div className="h-2 rounded-full bg-muted overflow-hidden">
            <div
              className={cn('h-full rounded-full transition-all duration-1000 ease-out', completionBarClass(trust.completion_bar_tier))}
              style={{ width: `${barWidth}%` }}
            />
          </div>
          <p className="text-[11px] text-muted-foreground">
            Completed {pct}% of orders successfully
          </p>
        </div>
      )}

      {/* Rating Breakdown */}
      {trust.rating_breakdown && (
        <div className="space-y-1.5 pt-1">
          <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Rating Breakdown</p>
          <div className="space-y-1">
            {Object.entries(trust.rating_breakdown)
              .sort(([a], [b]) => Number(b) - Number(a))
              .map(([rating, count]) => {
                const total = trust.reviews_total || 1;
                const width = Math.round((Number(count) / total) * 100);
                return (
                  <div key={rating} className="flex items-center gap-2 text-[10px]">
                    <span className="w-3 text-center">{rating}</span>
                    <Star className="w-2.5 h-2.5 fill-amber-400 text-amber-400" />
                    <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                      <div className="h-full bg-amber-400 rounded-full" style={{ width: `${width}%` }} />
                    </div>
                    <span className="w-4 text-right text-muted-foreground">{count}</span>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      <div className="grid gap-1.5 text-xs text-muted-foreground pt-1">
        {trust.last_shipped_text && (
          <div className={cn("flex items-center gap-2", trust.last_shipped_stale ? 'text-amber-600 dark:text-amber-400 font-medium' : '')}>
            <div className={cn("w-1.5 h-1.5 rounded-full", trust.last_shipped_stale ? 'bg-amber-500' : 'bg-emerald-500')} />
            {trust.last_shipped_text}
          </div>
        )}
        {trust.joined_text && (
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-blue-400" />
            {trust.joined_text}
          </div>
        )}
        {trust.response_time_text && (
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-purple-400" />
            {trust.response_time_text}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">Completed orders</span>
        <span className="font-medium text-foreground">
          {typeof trust.seller_tier_label === 'string' && /^\d+$/.test(trust.seller_tier_label)
            ? trust.seller_tier_label
            : trust.seller_tier_label}
        </span>
      </div>

      <div className="flex items-center gap-2">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div
                className={cn(
                  'flex items-center gap-1.5 rounded-lg border px-2 py-1 text-xs font-medium',
                  trust.identity_verified
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200'
                    : 'border-muted bg-muted/40 text-muted-foreground',
                )}
              >
                {trust.identity_verified ? (
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                ) : (
                  <Shield className="w-4 h-4" />
                )}
                {trust.identity_verified ? 'Identity Verified' : 'Identity not verified'}
              </div>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs text-sm">
              This means we have confirmed this seller&apos;s real identity using official ID documents.
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      {trust.reviews_preview && trust.reviews_preview.length > 0 && (
        <div className="space-y-2 pt-1 border-t">
          <p className="text-xs font-semibold text-foreground">Recent reviews</p>
          {trust.reviews_preview.map((r) => (
            <div key={r.id} className="rounded-lg bg-muted/40 p-2 space-y-1">
              <div className="flex items-center gap-1">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Star
                    key={i}
                    className={cn(
                      'w-3 h-3',
                      i < r.rating ? 'fill-amber-400 text-amber-400' : 'text-muted-foreground/30',
                    )}
                  />
                ))}
                <Badge variant="outline" className="text-[9px] h-4 px-1 ml-1">
                  Verified purchase
                </Badge>
              </div>
              <p className="text-xs font-medium text-foreground">{r.buyer_display}</p>
              {r.variant_summary && (
                <p className="text-[10px] text-muted-foreground">{r.variant_summary}</p>
              )}
              {r.comment && <p className="text-[11px] text-muted-foreground line-clamp-2">{r.comment}</p>}
              {r.media_urls && r.media_urls.length > 0 && (
                <div className="flex gap-1 pt-1">
                  {r.media_urls.slice(0, 2).map((url, idx) => (
                    <div key={idx} className="relative w-12 h-12 rounded-md overflow-hidden bg-muted">
                      <Image src={url} alt="" fill className="object-cover" sizes="48px" />
                    </div>
                  ))}
                </div>
              )}
              {r.seller_reply && (
                <p className="text-[10px] text-muted-foreground border-l-2 pl-2">Seller: {r.seller_reply}</p>
              )}
              <p className="text-[10px] text-muted-foreground">{getRelativeTime(r.created_at)}</p>
            </div>
          ))}
          {(reviewsTotal ?? trust.reviews_total) > trust.reviews_preview.length && (
            <Button variant="link" className="h-auto p-0 text-xs" type="button" onClick={onSeeAllReviews}>
              See all {(reviewsTotal ?? trust.reviews_total) || 0} reviews
            </Button>
          )}
        </div>
      )}

    </div>
  );
}
