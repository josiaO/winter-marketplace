'use client';

import { formatTZS, getDiscountPercent } from '@/lib/helpers';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface PriceDisplayProps {
  price: number;
  comparePrice?: number;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function PriceDisplay({
  price,
  comparePrice,
  size = 'md',
  className,
}: PriceDisplayProps) {
  const discount =
    comparePrice && comparePrice > price ? getDiscountPercent(price, comparePrice) : null;

  const sizeClasses = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
  };

  const priceClass = size === 'lg' ? 'text-xl font-bold' : 'font-bold';

  return (
    <div className={cn('flex flex-wrap items-baseline gap-2', className)}>
      <span
        className={cn(
          'text-green-600 dark:text-green-400',
          priceClass,
          sizeClasses[size]
        )}
      >
        {formatTZS(price)}
      </span>
      {comparePrice && comparePrice > price && (
        <>
          <span
            className={cn(
              'text-muted-foreground line-through',
              size === 'sm' ? 'text-xs' : 'text-sm'
            )}
          >
            {formatTZS(comparePrice)}
          </span>
          <Badge
            variant="secondary"
            className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 text-xs font-medium"
          >
            -{discount}%
          </Badge>
        </>
      )}
    </div>
  );
}
