'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '@/lib/api-client';
import { useAuthStore } from '@/store';

const MAX_RETRIES = 5;
const INITIAL_BACKOFF = 1000; // 1s

export function useNotifications(options: { disablePolling?: boolean } = {}) {
  const { isAuthenticated } = useAuthStore();
  const [unreadCount, setUnreadCount] = useState(0);
  const [lastNotificationId, setLastNotificationId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const { disablePolling } = options;

  const fetchUnreadCount = useCallback(async () => {
    if (!isAuthenticated) return;
    
    try {
      const res = await api.communications.notificationsUnreadCount();
      const anyRes = res as any;
      const count = anyRes.unread_count ?? anyRes.count ?? 0;
      setUnreadCount(count);
      return count;
    } catch (error: any) {
      console.error('[Notifications] Failed to fetch count:', error);
      return 0;
    }
  }, [isAuthenticated]);

  const connectWebSocket = useCallback(async () => {
    if (!isAuthenticated || disablePolling) return;

    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    try {
      // 1. Fetch short-lived ticket
      const { ticket } = await api.auth.fetchWsTicket();

      // 2. Resolve WebSocket URL
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const hostname = window.location.hostname;
      
      let host = hostname;
      if (hostname === 'localhost' || hostname === '127.0.0.1') {
        host = `${hostname}:8000`;
      } else if (window.location.port === '3000' || window.location.port === '3001') {
        host = `${hostname}:8000`;
      }

      const wsUrl = `${protocol}//${host}/ws/notifications/?ticket=${ticket}`;
      console.log(`[NotificationWS] Connecting... (retry: ${retryCountRef.current})`);
      
      const socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        console.log(`[NotificationWS] Connected`);
        retryCountRef.current = 0; // Reset retries on success
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'notification') {
            setUnreadCount((prev) => prev + 1);
          }
        } catch (err) {
          console.error('WS Notification parsing error:', err);
        }
      };

      socket.onerror = (error) => {
        console.error(`[NotificationWS] Error:`, error);
      };

      socket.onclose = (event) => {
        wsRef.current = null;
        if (event.code !== 1000 && isAuthenticated) {
          const delay = Math.min(INITIAL_BACKOFF * Math.pow(2, retryCountRef.current), 30000);
          if (retryCountRef.current < MAX_RETRIES) {
            console.warn(`[NotificationWS] Closed (${event.code}). Retrying in ${delay}ms...`);
            retryCountRef.current++;
            reconnectTimeoutRef.current = setTimeout(connectWebSocket, delay);
          } else {
            console.error('[NotificationWS] Max retries reached.');
          }
        }
      };

      wsRef.current = socket;
    } catch (err) {
      console.error('[NotificationWS] Failed to initiate connection:', err);
    }
  }, [isAuthenticated, disablePolling]);

  useEffect(() => {
    if (isAuthenticated && !disablePolling) {
      fetchUnreadCount();
      connectWebSocket();
    }
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close(1000);
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [isAuthenticated, disablePolling, fetchUnreadCount, connectWebSocket]);

  return {
    unreadCount,
    lastNotificationId,
    setLastNotificationId,
    refresh: fetchUnreadCount,
    isLoading,
  };
}
