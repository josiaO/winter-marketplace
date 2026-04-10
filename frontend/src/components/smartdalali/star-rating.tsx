'use client';

import { Star, StarHalf } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StarRatingProps {
  rating: number;
  size?: number;
  showCount?: boolean;
  count?: number;
  interactive?: boolean;
  onRate?: (rating: number) => void;
  className?: string;
}

export function StarRating({
  rating,
  size = 16,
  showCount = false,
  count,
  interactive = false,
  onRate,
  className,
}: StarRatingProps) {
  const stars: React.ReactNode[] = [];
  const fullStars = Math.floor(rating);
  const hasHalfStar = rating - fullStars >= 0.5;
  const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0);

  for (let i = 0; i < fullStars; i++) {
    stars.push(
      <Star
        key={`full-${i}`}
        className={cn(
          'fill-amber-400 text-amber-400',
          interactive && 'cursor-pointer hover:scale-110 transition-transform'
        )}
        size={size}
        onClick={interactive ? () => onRate?.(i + 1) : undefined}
      />
    );
  }

  if (hasHalfStar) {
    stars.push(
      <StarHalf
        key="half"
        className={cn(
          'fill-amber-400 text-amber-400',
          interactive && 'cursor-pointer hover:scale-110 transition-transform'
        )}
        size={size}
        onClick={interactive ? () => onRate?.(fullStars + 1) : undefined}
      />
    );
  }

  for (let i = 0; i < emptyStars; i++) {
    stars.push(
      <Star
        key={`empty-${i}`}
        className={cn(
          'text-gray-300 dark:text-gray-600',
          interactive && 'cursor-pointer hover:scale-110 transition-transform'
        )}
        size={size}
        onClick={interactive ? () => onRate?.(fullStars + (hasHalfStar ? 1 : 0) + i + 1) : undefined}
      />
    );
  }

  return (
    <div className={cn('flex items-center gap-1', className)}>
      <div className="flex items-center">{stars}</div>
      {showCount && count !== undefined && (
        <span className="text-sm text-muted-foreground ml-1">
          ({count})
        </span>
      )}
    </div>
  );
}
