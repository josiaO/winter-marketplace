'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageSquare,
  Loader2,
  Package,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { EmptyState } from '@/components/smartdalali/empty-state';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, getRelativeTime, getInitials } from '@/lib/helpers';
import { toast } from 'sonner';
import type { Conversation } from '@/types/api';
import { cn } from '@/lib/utils';

// ── Inbox View ──────────────────────────────────────────────────────────────

function InboxView() {
  const router = useRouter();
  const { isAuthenticated, user } = useAuthStore();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchConversations = useCallback(async () => {
    if (!isAuthenticated) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const res = await api.communications.conversations({ page: 1, page_size: 50 });
      // Handle both paginated and non-paginated responses
      if (Array.isArray(res)) {
        setConversations(res);
      } else if (res && typeof res === 'object' && 'results' in res) {
        setConversations(res.results || []);
      } else {
        setConversations([]);
      }
    } catch {
      toast.error('Failed to load conversations');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-8 w-40 mb-6" />
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 p-4 rounded-xl border">
              <Skeleton className="w-12 h-12 rounded-full flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-3 w-2/3" />
              </div>
              <Skeleton className="h-3 w-16" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
            Messages
          </h1>
          <span className="text-sm text-muted-foreground">
            {conversations.length} {conversations.length === 1 ? 'conversation' : 'conversations'}
          </span>
        </div>

        {conversations.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="No conversations yet"
            description="When you message a seller or a buyer reaches out, your conversations will appear here."
            actionLabel="Browse Products"
            onAction={() => router.push(routes.home())}
          />
        ) : (
          <div className="space-y-2">
            <AnimatePresence>
              {conversations.map((conversation, index) => {
                const otherParticipant = conversation.other_participant || (conversation.participants && conversation.participants.length > 0
                  ? conversation.participants.find((p: any) => p.id !== user?.id) || conversation.participants[0]
                  : null);

                const lastMessage = conversation.last_message;

                return (
                  <motion.div
                    key={conversation.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.03 }}
                    className={cn(
                      'flex items-center gap-3 p-3 sm:p-4 rounded-xl border bg-card cursor-pointer',
                      'hover:shadow-md transition-shadow',
                      conversation.unread_count > 0 && 'bg-emerald-50/50 dark:bg-emerald-950/10 border-emerald-200 dark:border-emerald-800'
                    )}
                    onClick={() =>
                      router.push(routes.messageThread(String(conversation.id)))
                    }
                  >
                    {/* Avatar */}
                    <div className="relative flex-shrink-0">
                      <Avatar className="w-11 h-11 sm:w-12 sm:h-12">
                        <AvatarImage
                          src={otherParticipant?.avatar || undefined}
                          alt={otherParticipant?.username || ''}
                        />
                        <AvatarFallback className="bg-primary/10 text-primary text-sm font-semibold">
                          {getInitials(
                            otherParticipant?.first_name && otherParticipant?.last_name
                              ? `${otherParticipant.first_name} ${otherParticipant.last_name}`
                              : otherParticipant?.username || 'U'
                          )}
                        </AvatarFallback>
                      </Avatar>
                      {conversation.unread_count > 0 && (
                        <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-emerald-500 text-white text-xs flex items-center justify-center font-bold">
                          {conversation.unread_count > 9 ? '9+' : conversation.unread_count}
                        </span>
                      )}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <h3 className={cn(
                          'text-sm font-medium truncate',
                          conversation.unread_count > 0
                            ? 'font-semibold text-foreground'
                            : 'text-foreground'
                        )}>
                          {otherParticipant?.full_name || otherParticipant?.username || 'User'}
                        </h3>
                        {lastMessage && (
                          <span className="text-xs text-muted-foreground flex-shrink-0">
                            {getRelativeTime(lastMessage.created_at)}
                          </span>
                        )}
                      </div>

                      {/* Listing context */}
                      {conversation.listing && (
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <Package className="w-3 h-3 text-muted-foreground" />
                          <span className="text-xs text-muted-foreground truncate">
                            {conversation.listing.title}
                          </span>
                        </div>
                      )}

                      {/* Last message preview */}
                      {lastMessage && (
                        <p className={cn(
                          'text-xs mt-1 truncate',
                          conversation.unread_count > 0
                            ? 'text-foreground font-medium'
                            : 'text-muted-foreground'
                        )}>
                          {lastMessage.sender === user?.id ? 'You: ' : ''}
                          {lastMessage.text}
                        </p>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </motion.div>
    </div>
  );
}

// ── Main Messages Page ──────────────────────────────────────────────────────

export function MessagesPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  useEffect(() => {
    if (!isAuthenticated) {
      router.push(routes.login());
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return <InboxView />;
}
