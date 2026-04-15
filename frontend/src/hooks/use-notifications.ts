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
  const wsRef = useRef<WebSocket | null>(null);

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
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
      }
      return 0;
    }
  }, [isAuthenticated]);

  const stopPolling = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    let isMounted = true;

    if (isAuthenticated && !disablePolling && !globalFatalError) {
      // 1. Initial fetch
      fetchUnreadCount();
      
      // 2. Setup WebSocket connection for real-time notifications
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const hostname = window.location.hostname;
      
      // Map frontend hostname to backend API port (8000) for local development
      let host = hostname;
      if (hostname === 'localhost' || hostname === '127.0.0.1') {
        host = `${hostname}:8000`;
      } else if (window.location.port === '3000' || window.location.port === '3001') {
        // Handle cases where we might be using a public tunnel or custom port
        host = `${hostname}:8000`;
      }

      // 1. Resolve Token: Direct ApiClient access bypasses Zustand hydration delay
      const token = useAuthStore.getState().accessToken || api.getAccessToken();
      const wsUrl = `${protocol}//${host}/ws/notifications/`;
      const b64url = (str: string) => btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
      
      const socket = token 
        ? new WebSocket(wsUrl, ['sd-jwt', b64url(token)])
        : new WebSocket(wsUrl);

      console.log(`[NotificationWS] Connecting to ${wsUrl} (auth: ${!!token}, source: ${token === useAuthStore.getState().accessToken ? 'store' : 'api'})`);
      
      socket.onopen = () => {
        console.log(`[NotificationWS] Connected to ${wsUrl}`);
      };

      socket.onerror = (error) => {
        console.error(`[NotificationWS] Connection error for ${wsUrl}:`, error);
      };

      socket.onclose = (event) => {
        if (event.code !== 1000) {
          console.warn(`[NotificationWS] Closed unexpectedly (${event.code}) for ${wsUrl}`);
        }
      };

      wsRef.current = socket;

      socket.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'notification') {
            // Increment unread count locally when a new notification comes in
            // This will trigger the NotificationProvider to fetch the latest notification and show a toast
            setUnreadCount((prev) => prev + 1);
          }
        } catch (err) {
          console.error('WS Notification parsing error:', err);
        }
      };
    }
    
    return () => {
      isMounted = false;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
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
