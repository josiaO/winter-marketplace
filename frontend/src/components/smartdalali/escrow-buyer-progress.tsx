'use client';

import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Order, OrderStatus } from '@/types/api';
import type { OrderEscrowSnapshot } from '@/lib/marketplace-order-payment';

const STEPS: { label: string; emoji: string }[] = [
  { label: 'You Paid', emoji: '💳' },
  { label: 'Funds Held', emoji: '🔒' },
  { label: 'Seller Ships', emoji: '📦' },
  { label: 'You Confirm', emoji: '✅' },
  { label: 'Seller Paid', emoji: '💰' },
];

function activeStepIndex(order: Order, escrow: OrderEscrowSnapshot | undefined): number {
  const st = order.status as OrderStatus;
  const es = (escrow?.status || '').toUpperCase();

  if (st === 'pending') return 0;
  if (st === 'disputed') return 1;
  if (st === 'cancelled' || st === 'refunded') return 0;
  if (st === 'confirmed' || st === 'processing') return 1;
  if (st === 'shipped' || st === 'arrived') return 2;
  if (st === 'delivered') return 3;
  if (st === 'completed') return es === 'RELEASED' ? 4 : 3;
  return 0;
}

export function EscrowBuyerProgress({ order }: { order: Order }) {
  const escrow = (order as { escrow?: OrderEscrowSnapshot }).escrow;
  const active = activeStepIndex(order, escrow);

  return (
    <div className="rounded-xl border bg-gradient-to-b from-muted/30 to-card p-4">
      <p className="text-xs font-semibold text-foreground mb-3">Escrow protection</p>
      <div className="flex items-start justify-between gap-1 overflow-x-auto pb-1">
        {STEPS.map((s, i) => {
          const done = i < active;
          const current = i === active;
          return (
            <div key={s.label} className="flex flex-1 min-w-[56px] flex-col items-center gap-1">
              <div
                className={cn(
                  'flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 text-sm',
                  done && 'border-emerald-500 bg-emerald-500 text-white',
                  current && !done && 'border-primary bg-primary/10 text-primary ring-2 ring-primary/20',
                  !done && !current && 'border-muted-foreground/25 bg-muted/50 text-muted-foreground',
                )}
              >
                {done ? <Check className="w-4 h-4" /> : <span aria-hidden>{s.emoji}</span>}
              </div>
              <span
                className={cn(
                  'text-[9px] font-medium text-center leading-tight px-0.5',
                  current ? 'text-primary' : done ? 'text-emerald-700 dark:text-emerald-400' : 'text-muted-foreground',
                )}
              >
                {s.label}
              </span>
            </div>
          );
        })}
      </div>
      <p className="text-[11px] text-muted-foreground mt-3">
        Funds stay with SmartDalali until you confirm you received your order.
      </p>
    </div>
  );
}
