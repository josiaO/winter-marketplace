'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bell,
  Package,
  CreditCard,
  MessageSquare,
  Star,
  ShieldCheck,
  Settings,
  AlertTriangle,
  Wallet,
  Megaphone,
  CheckCheck,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { EmptyState } from '@/components/smartdalali/empty-state';
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { getRelativeTime } from '@/lib/helpers';
import { toast } from 'sonner';
import type { Notification, NotificationType } from '@/types/api';
import { cn } from '@/lib/utils';
import { type LucideIcon } from 'lucide-react';

// ── Notification type icon & color map ──────────────────────────────────────

const NOTIFICATION_CONFIG: Record<
  NotificationType,
  { icon: LucideIcon; bg: string; color: string }
> = {
  order: {
    icon: Package,
    bg: 'bg-blue-100 dark:bg-blue-900/30',
    color: 'text-blue-600 dark:text-blue-400',
  },
  payment: {
    icon: CreditCard,
    bg: 'bg-green-100 dark:bg-green-900/30',
    color: 'text-green-600 dark:text-green-400',
  },
  message: {
    icon: MessageSquare,
    bg: 'bg-emerald-100 dark:bg-emerald-900/30',
    color: 'text-emerald-600 dark:text-emerald-400',
  },
  listing: {
    icon: Package,
    bg: 'bg-purple-100 dark:bg-purple-900/30',
    color: 'text-purple-600 dark:text-purple-400',
  },
  review: {
    icon: Star,
    bg: 'bg-yellow-100 dark:bg-yellow-900/30',
    color: 'text-yellow-600 dark:text-yellow-400',
  },
  verification: {
    icon: ShieldCheck,
    bg: 'bg-teal-100 dark:bg-teal-900/30',
    color: 'text-teal-600 dark:text-teal-400',
  },
  system: {
    icon: Settings,
    bg: 'bg-gray-100 dark:bg-gray-900/30',
    color: 'text-gray-600 dark:text-gray-400',
  },
  dispute: {
    icon: AlertTriangle,
    bg: 'bg-red-100 dark:bg-red-900/30',
    color: 'text-red-600 dark:text-red-400',
  },
  payout: {
    icon: Wallet,
    bg: 'bg-emerald-100 dark:bg-emerald-900/30',
    color: 'text-emerald-600 dark:text-emerald-400',
  },
  promotion: {
    icon: Megaphone,
    bg: 'bg-orange-100 dark:bg-orange-900/30',
    color: 'text-orange-600 dark:text-orange-400',
  },
};

// ── Notification Item ───────────────────────────────────────────────────────

function NotificationItem({ notification }: { notification: Notification }) {
  const config = NOTIFICATION_CONFIG[notification.type] || NOTIFICATION_CONFIG.system;
  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'flex items-start gap-3 p-3 sm:p-4 rounded-xl transition-colors',
        !notification.is_read
          ? 'bg-emerald-50/50 dark:bg-emerald-950/10 border border-emerald-200 dark:border-emerald-800'
          : 'bg-card hover:bg-muted/30 border border-transparent'
      )}
    >
      {/* Icon */}
      <div
        className={cn(
          'w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0',
          config.bg
        )}
      >
        <Icon className={cn('w-5 h-5', config.color)} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-0.5">
        <div className="flex items-start justify-between gap-2">
          <h3
            className={cn(
              'text-sm leading-snug',
              !notification.is_read ? 'font-semibold text-foreground' : 'font-medium text-foreground'
            )}
          >
            {notification.title}
          </h3>
          <span className="text-xs text-muted-foreground flex-shrink-0 whitespace-nowrap">
            {getRelativeTime(notification.created_at)}
          </span>
        </div>
        <p
          className={cn(
            'text-sm leading-relaxed',
            !notification.is_read ? 'text-foreground' : 'text-muted-foreground'
          )}
        >
          {notification.body}
        </p>
      </div>

      {/* Unread indicator */}
      {!notification.is_read && (
        <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 flex-shrink-0 mt-2" />
      )}
    </motion.div>
  );
}

// ── Main Notifications Page ─────────────────────────────────────────────────

export function NotificationsPage() {
  const { navigate } = useUIStore();
  const { isAuthenticated } = useAuthStore();

  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isMarkingAll, setIsMarkingAll] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

  const fetchNotifications = useCallback(
    async (page = 1) => {
      if (!isAuthenticated) {
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      try {
        const res = await api.communications.notifications({ page, page_size: 20 });
        if (page === 1) {
          setNotifications(res.results || []);
        } else {
          setNotifications((prev) => [...prev, ...(res.results || [])]);
        }
        setHasMore(!!res.next);
        setCurrentPage(page);
      } catch {
        toast.error('Failed to load notifications');
      } finally {
        setIsLoading(false);
      }
    },
    [isAuthenticated]
  );

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const handleMarkAllRead = async () => {
    setIsMarkingAll(true);
    try {
      await api.communications.markAllNotificationsRead();
      setNotifications((prev) =>
        prev.map((n) => ({ ...n, is_read: true }))
      );
      toast.success('All notifications marked as read');
    } catch {
      toast.error('Failed to mark notifications as read');
    } finally {
      setIsMarkingAll(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex items-center justify-between mb-6">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-9 w-32 rounded-lg" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex items-start gap-3 p-4 rounded-xl border">
              <Skeleton className="w-10 h-10 rounded-full flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-1/4" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <EmptyState
          icon={Bell}
          title="Please login to view notifications"
          description="You need to be logged in to see your notifications."
          actionLabel="Login"
          onAction={() => navigate({ view: 'login' })}
        />
      </div>
    );
  }

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
              Notifications
            </h1>
            {unreadCount > 0 && (
              <Badge className="bg-emerald-500 text-white text-xs">
                {unreadCount} new
              </Badge>
            )}
          </div>

          {unreadCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5 rounded-full"
              onClick={handleMarkAllRead}
              disabled={isMarkingAll}
            >
              {isMarkingAll ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <CheckCheck className="w-4 h-4" />
              )}
              Mark all as read
            </Button>
          )}
        </div>

        {/* Notifications List */}
        {notifications.length === 0 ? (
          <EmptyState
            icon={Bell}
            title="No notifications yet"
            description="When something important happens, we'll let you know. Notifications about orders, messages, and more will appear here."
          />
        ) : (
          <div className="space-y-2">
            <AnimatePresence>
              {notifications.map((notification) => (
                <NotificationItem
                  key={notification.id}
                  notification={notification}
                />
              ))}
            </AnimatePresence>

            {/* Load More */}
            {hasMore && (
              <div className="flex justify-center pt-4">
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full"
                  onClick={() => fetchNotifications(currentPage + 1)}
                >
                  Load more notifications
                </Button>
              </div>
            )}
          </div>
        )}
      </motion.div>
    </div>
  );
}
