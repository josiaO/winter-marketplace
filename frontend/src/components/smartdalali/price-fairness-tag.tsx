'use client';

import { Info } from 'lucide-react';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import type { PriceFairness } from '@/types/api';

const COPY: Record<
  NonNullable<PriceFairness['indicator']>,
  { label: string; tooltip: string; className: string }
> = {
  none: { label: '', tooltip: '', className: '' },
  below_average: {
    label: 'Below average price',
    tooltip:
      'This product is priced lower than similar items. This may be a great deal or worth verifying with the seller.',
    className: 'bg-sky-100 text-sky-900 dark:bg-sky-950/50 dark:text-sky-200 border-sky-200 dark:border-sky-800',
  },
  above_average: {
    label: 'Above average price',
    tooltip:
      'This product is priced higher than similar items. Check the seller’s ratings before buying.',
    className: 'bg-amber-100 text-amber-950 dark:bg-amber-950/40 dark:text-amber-100 border-amber-200 dark:border-amber-800',
  },
  unusual_low: {
    label: 'Unusually low price — buyer caution',
    tooltip:
      'This price is significantly below market rate. We recommend reviewing the seller’s history carefully before paying.',
    className: 'bg-red-100 text-red-950 dark:bg-red-950/40 dark:text-red-100 border-red-200 dark:border-red-900',
  },
};

export function PriceFairnessTag({ fairness }: { fairness?: PriceFairness | null }) {
  if (!fairness || !fairness.indicator || fairness.indicator === 'none') return null;
  const cfg = COPY[fairness.indicator];
  if (!cfg.label) return null;
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn(
              'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium cursor-help max-w-[200px] truncate',
              cfg.className,
            )}
          >
            <span aria-hidden>{fairness.indicator === 'below_average' ? '🔵' : fairness.indicator === 'above_average' ? '🟡' : '🔴'}</span>
            {cfg.label}
            <Info className="w-3 h-3 opacity-70 shrink-0" />
          </span>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-sm">
          {cfg.tooltip}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
