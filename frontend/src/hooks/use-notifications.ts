'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '@/lib/api-client';
import { useAuthStore } from '@/store';

let globalFatalError = false;

export function useNotifications(options: { disablePolling?: boolean } = {}) {
  const { isAuthenticated } = useAuthStore();
  const [unreadCount, setUnreadCount] = useState(0);
  const [lastNotificationId, setLastNotificationId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const { disablePolling } = options;

  const fetchUnreadCount = useCallback(async () => {
    // Only fetch if authenticated AND no fatal error occured (e.g. 403 Forbidden)
    if (!isAuthenticated || !api.getAccessToken() || globalFatalError) return;
    
    try {
      const res = await api.communications.notificationsUnreadCount();
      const anyRes = res as any;
      const count = anyRes.unread_count ?? anyRes.count ?? 0;
      setUnreadCount(count);
      return count;
    } catch (error: any) {
      // If we get a 401/403, stop polling permanently for this session
      if (error.status === 401 || error.status === 403) {
        globalFatalError = true;
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
      }
      return 0;
    }
  }, [isAuthenticated]);

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    let isMounted = true;

    const tick = async () => {
      if (!isMounted || globalFatalError || document.visibilityState !== 'visible') return;
      await fetchUnreadCount();
    };

    if (isAuthenticated && !disablePolling && !globalFatalError) {
      // Initial fetch
      tick();
      
      // Setup interval
      pollIntervalRef.current = setInterval(tick, 60000);
    }
    
    return () => {
      isMounted = false;
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [isAuthenticated, disablePolling, fetchUnreadCount]);

  return {
    unreadCount,
    lastNotificationId,
    setLastNotificationId,
    refresh: fetchUnreadCount,
    isLoading,
  };
}
