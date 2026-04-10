'use client';

import React, { createContext, useContext, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { Bell } from 'lucide-react';
import { useNotifications } from '@/hooks/use-notifications';
import { api } from '@/lib/api-client';
import { useAuthStore } from '@/store';

interface NotificationContextType {
  unreadCount: number;
  refresh: () => Promise<number | undefined>;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  const { unreadCount, lastNotificationId, setLastNotificationId, refresh } = useNotifications();
  const prevCountRef = useRef(0);

  useEffect(() => {
    if (!isAuthenticated) return;

    // Check if unread count increased
    if (unreadCount > prevCountRef.current) {
      // Fetch latest notifications to show the most recent one
      const fetchLatest = async () => {
        try {
          const res = await api.communications.notifications({ limit: 1 });
          const latest = res.results?.[0];
          
          if (latest && latest.id !== lastNotificationId) {
            setLastNotificationId(latest.id);
            
            // Trigger toast
            toast(latest.title || 'New Notification', {
              description: latest.message,
              icon: <Bell className="w-4 h-4 text-primary" />,
              action: {
                label: 'View',
                onClick: () => {
                  // Logic to navigate or mark as read
                  // For now just mark as read implicitly by opening
                }
              }
            });
          }
        } catch (error) {
          console.error('Failed to fetch latest notification for toast:', error);
        }
      };

      void fetchLatest();
    }
    
    prevCountRef.current = unreadCount;
  }, [unreadCount, isAuthenticated, lastNotificationId, setLastNotificationId]);

  return (
    <NotificationContext.Provider value={{ unreadCount, refresh }}>
      {children}
    </NotificationContext.Provider>
  );
}

export const useNotificationContext = () => {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error('useNotificationContext must be used within a NotificationProvider');
  }
  return context;
};
