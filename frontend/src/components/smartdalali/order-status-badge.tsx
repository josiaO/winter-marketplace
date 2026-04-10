'use client';

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { getStatusColor, getStatusLabel } from '@/lib/helpers';
import { OrderStatus } from '@/types';

interface OrderStatusBadgeProps {
  status: OrderStatus | string;
  className?: string;
}

export function OrderStatusBadge({ status, className }: OrderStatusBadgeProps) {
  return (
    <Badge
      variant="secondary"
      className={cn(
        'font-medium text-xs px-2.5 py-0.5 rounded-full',
        getStatusColor(status),
        className
      )}
    >
      {getStatusLabel(status)}
    </Badge>
  );
}
