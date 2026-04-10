import { OrderStatus, type Listing, type ListingImage } from '@/types';

/**
 * Format an amount in Tanzanian Shillings
 */
export function formatTZS(amount: number): string {
  return `TZS ${amount.toLocaleString('en-TZ')}`;
}

/**
 * Format a date string to a readable format
 */
export function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-TZ', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Format a date string with time
 */
export function formatDateTime(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-TZ', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Calculate discount percentage between price and compare price
 */
export function getDiscountPercent(price: number, comparePrice: number): number {
  if (comparePrice <= 0 || price <= 0) return 0;
  return Math.round(((comparePrice - price) / comparePrice) * 100);
}

/**
 * Get the color class for an order status
 */
export function getStatusColor(status: OrderStatus | string): string {
  const colors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
    confirmed: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    processing: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    shipped: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
    delivered: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    completed: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    cancelled: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    created: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
    paid: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
    failed: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
    refunded: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
  };
  return colors[status] || colors.pending;
}

/**
 * Get human-readable label for an order status
 */
export function getStatusLabel(status: OrderStatus | string): string {
  const labels: Record<string, string> = {
    pending: 'Pending',
    confirmed: 'Confirmed',
    processing: 'Processing',
    shipped: 'Shipped',
    delivered: 'Delivered',
    completed: 'Completed',
    cancelled: 'Cancelled',
    created: 'Created',
    paid: 'Paid',
    failed: 'Failed',
    refunded: 'Refunded',
  };
  return labels[status] || status;
}

/**
 * Truncate text to a maximum length with ellipsis
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '…';
}

/**
 * Get relative time string (e.g. "2 hours ago")
 */
export function getRelativeTime(dateString: string): string {
  const now = new Date();
  const date = new Date(dateString);
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);
  const diffWeeks = Math.floor(diffDays / 7);
  const diffMonths = Math.floor(diffDays / 30);

  if (diffSeconds < 60) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffWeeks < 4) return `${diffWeeks}w ago`;
  if (diffMonths < 12) return `${diffMonths}mo ago`;
  return formatDate(dateString);
}

/**
 * Generate initials from a name
 */
export function getInitials(name: string): string {
  return name
    .split(' ')
    .map((word) => word[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

/**
 * Normalize a listing from the list API into the full Listing type.
 * The list API returns `image` (string) and omits `seller.username` / `seller.isVerified`.
 * This helper converts it to match the Listing type used by ProductCard etc.
 */
export function normalizeListing(raw: Record<string, unknown>): Listing {
  const l = raw as any;
  const images: ListingImage[] = Array.isArray(l.images) && l.images.length > 0
    ? l.images
    : l.image
      ? [{ id: '__img', url: l.image, altText: '', sortOrder: 0, isPrimary: true }]
      : [];

  const seller = l.seller || {};
  return {
    ...l,
    images,
    _count: l._count || { reviews: l.reviewsCount || 0 },
    seller: {
      id: seller.id || '',
      username: seller.username || seller.name || '',
      avatar: seller.avatar,
      isVerified: !!seller.isVerified,
    },
    avgRating: l.avgRating ?? l.averageRating ?? 0,
    categoryId: l.categoryId || l.category?.id || '',
    category: l.category || { id: '', name: '', slug: '' },
  };
}

/** OrderSerializer exposes total_amount / totalAmount; normalize for display. */
export function orderTotalAmount(order: {
  total?: number;
  totalAmount?: string | number;
  total_amount?: string | number;
}): number {
  const raw = order.totalAmount ?? order.total_amount ?? order.total;
  if (raw === undefined || raw === null) return 0;
  return typeof raw === 'string' ? parseFloat(raw) : Number(raw);
}

export function orderNumberLabel(order: {
  order_number?: string;
  orderNumber?: string;
  id?: number;
}): string {
  return order.orderNumber || order.order_number || (order.id != null ? `ORD-${String(order.id).padStart(8, '0')}` : '');
}
