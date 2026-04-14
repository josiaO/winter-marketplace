import { motion } from 'framer-motion';
import { Check, Lock, ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Order, OrderStatus } from '@/types/api';
import type { OrderEscrowSnapshot } from '@/lib/marketplace-order-payment';

const STEPS: { label: string; emoji: string; description: string }[] = [
  { label: 'You Paid', emoji: '💳', description: 'Payment received by platform' },
  { label: 'Funds Held', emoji: '🔒', description: 'Money locked in secure escrow' },
  { label: 'Seller Ships', emoji: '📦', description: 'Item is on its way to you' },
  { label: 'You Confirm', emoji: '✅', description: 'Verify you got what you ordered' },
  { label: 'Seller Paid', emoji: '💰', description: 'Funds released to the seller' },
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
    <div className="rounded-2xl border bg-gradient-to-b from-emerald-50/50 to-white dark:from-emerald-950/10 dark:to-card p-5 shadow-sm overflow-hidden relative">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-emerald-600" />
          <p className="text-sm font-bold text-foreground">Escrow Protection Active</p>
        </div>
        {active >= 1 && active < 4 && (
          <Badge variant="secondary" className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 gap-1 animate-pulse">
            <Lock className="w-3 h-3" />
            Funds Secured
          </Badge>
        )}
      </div>

      <div className="flex items-start justify-between relative">
        {/* Background Line */}
        <div className="absolute top-[18px] left-[10%] right-[10%] h-0.5 bg-muted z-0" />
        
        {/* Progress Line */}
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${(active / (STEPS.length - 1)) * 80}%` }}
          className="absolute top-[18px] left-[10%] h-0.5 bg-emerald-500 z-0 transition-all duration-1000 ease-in-out"
        />

        {STEPS.map((s, i) => {
          const done = i < active;
          const current = i === active;
          return (
            <div key={s.label} className="flex flex-col items-center gap-2 z-10 w-full">
              <motion.div
                initial={false}
                animate={{
                  scale: current ? 1.1 : 1,
                  backgroundColor: done ? '#10b981' : current ? 'white' : '#f3f4f6',
                  borderColor: done ? '#10b981' : current ? '#10b981' : '#e5e7eb'
                }}
                className={cn(
                  'flex h-9 w-9 items-center justify-center rounded-full border-2 text-sm shadow-sm transition-colors',
                  current && 'ring-4 ring-emerald-500/10'
                )}
              >
                {done ? (
                  <Check className="w-5 h-5 text-white" />
                ) : (
                  <span className={cn(current ? 'opacity-100' : 'opacity-50')}>{s.emoji}</span>
                )}
              </motion.div>
              <div className="flex flex-col items-center">
                <span
                  className={cn(
                    'text-[10px] font-bold text-center leading-tight',
                    current ? 'text-foreground' : done ? 'text-emerald-600' : 'text-muted-foreground',
                  )}
                >
                  {s.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <motion.div 
        layout
        className="mt-6 p-3 rounded-xl bg-muted/30 border border-dashed text-center"
      >
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          {STEPS[active].description}. SmartDalali holds the funds safely until you are satisfied.
        </p>
      </motion.div>
    </div>
  );
}

import { Badge } from '@/components/ui/badge';
