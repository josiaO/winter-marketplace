'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '@/lib/api-client';
import { useAuthStore } from '@/store';

export function useNotifications() {
  const { isAuthenticated } = useAuthStore();
  const [unreadCount, setUnreadCount] = useState(0);
  const [lastNotificationId, setLastNotificationId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchUnreadCount = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const res = await api.communications.notificationsUnreadCount();
      const anyRes = res as any;
      const count = anyRes.unread_count ?? anyRes.count ?? 0;
      setUnreadCount(count);
      return count;
    } catch (error) {
      console.error('Failed to fetch notifications unread count:', error);
      return 0;
    }
  }, [isAuthenticated]);

  const startPolling = useCallback(() => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    
    // Initial fetch
    fetchUnreadCount();
    
    // Poll every 45 seconds for production efficiency
    pollIntervalRef.current = setInterval(fetchUnreadCount, 45000);
  }, [fetchUnreadCount]);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      startPolling();
    } else {
      setUnreadCount(0);
      stopPolling();
    }
    
    return () => stopPolling();
  }, [isAuthenticated, startPolling, stopPolling]);

  return {
    unreadCount,
    lastNotificationId,
    setLastNotificationId,
    refresh: fetchUnreadCount,
    isLoading,
  };
}
