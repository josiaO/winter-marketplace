'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageSquare,
  Send,
  ArrowLeft,
  Package,
  FileText,
  Image as ImageIcon,
  Loader2,
  Search,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { EmptyState } from '@/components/smartdalali/empty-state';
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatTZS, getRelativeTime, getInitials } from '@/lib/helpers';
import { toast } from 'sonner';
import type { Conversation, Message, ConversationParticipant } from '@/types/api';
import { cn } from '@/lib/utils';

// ── Inbox View ──────────────────────────────────────────────────────────────

function InboxView() {
  const { navigate, currentView } = useUIStore();
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
      setConversations(res.results || []);
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
            onAction={() => navigate({ view: 'home' })}
          />
        ) : (
          <div className="space-y-2">
            <AnimatePresence>
              {conversations.map((conversation, index) => {
                const otherParticipant = conversation.participants.find(
                  (p) => p.id !== user?.id
                ) || conversation.participants[0];

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
                      navigate({ view: 'conversation', id: String(conversation.id) })
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
                          {otherParticipant?.first_name && otherParticipant?.last_name
                            ? `${otherParticipant.first_name} ${otherParticipant.last_name}`
                            : otherParticipant?.username || 'Unknown User'}
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
                          {lastMessage.content}
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

// ── Conversation Thread View ────────────────────────────────────────────────

function ConversationThread({ conversationId }: { conversationId: string }) {
  const { navigate, currentView } = useUIStore();
  const { isAuthenticated, user } = useAuthStore();

  const [messages, setMessages] = useState<Message[]>([]);
  const [participants, setParticipants] = useState<ConversationParticipant[]>([]);
  const [listing, setListing] = useState<Conversation['listing']>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [newMessage, setNewMessage] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    if (scrollAreaRef.current) {
      const viewport = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight;
      }
    }
  }, []);

  const fetchMessages = useCallback(async () => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    try {
      const res = await api.communications.messages(conversationId, {
        page: 1,
        page_size: 100,
      });
      setMessages(res.results || []);

      // Mark as read
      await api.communications.markRead(conversationId).catch(() => {});

      // Fetch conversation details for participants
      const convRes = await api.communications.conversations();
      const conv = convRes.results?.find((c) => String(c.id) === String(conversationId));
      if (conv) {
        setParticipants(conv.participants || []);
        setListing(conv.listing || null);
      }
    } catch {
      toast.error('Failed to load messages');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, conversationId]);

  useEffect(() => {
    fetchMessages();
  }, [fetchMessages]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSend = async () => {
    if (!newMessage.trim() || sendingMessage) return;

    setSendingMessage(true);
    const content = newMessage.trim();
    setNewMessage('');

    try {
      const sent = await api.communications.sendMessage(conversationId, { content });
      setMessages((prev) => [...prev, sent]);
      toast.success('Message sent');
    } catch {
      toast.error('Failed to send message');
      setNewMessage(content);
    } finally {
      setSendingMessage(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const otherParticipant = participants.find((p) => p.id !== user?.id) || participants[0];

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-8 w-40 mb-6" />
        <div className="rounded-xl border overflow-hidden">
          <div className="p-4 border-b flex items-center gap-3">
            <Skeleton className="w-12 h-12 rounded-full" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-20" />
            </div>
          </div>
          <div className="p-4 space-y-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className={cn('flex gap-2', i % 2 === 0 ? 'justify-start' : 'justify-end')}>
                <Skeleton className={cn('h-12 w-48 rounded-2xl', i % 2 === 0 ? '' : 'bg-primary/10')} />
              </div>
            ))}
          </div>
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
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 rounded-full"
            onClick={() => navigate({ view: 'messages' })}
          >
            <ArrowLeft className="w-4 h-4" />
          </Button>
          <Avatar className="w-10 h-10">
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
          <div className="flex-1 min-w-0">
            <h1 className="text-base sm:text-lg font-semibold text-foreground truncate">
              {otherParticipant?.first_name && otherParticipant?.last_name
                ? `${otherParticipant.first_name} ${otherParticipant.last_name}`
                : otherParticipant?.username || 'Unknown User'}
            </h1>
            {listing && (
              <p className="text-xs text-muted-foreground truncate">
                Re: {listing.title}
              </p>
            )}
          </div>
          {listing && (
            <Button
              variant="outline"
              size="sm"
              className="hidden sm:flex gap-1.5"
              onClick={() => navigate({ view: 'product', id: String(listing.id) })}
            >
              <Package className="w-3.5 h-3.5" />
              View Listing
            </Button>
          )}
        </div>

        {/* Messages Area */}
        <div className="rounded-xl border bg-card overflow-hidden">
          <ScrollArea className="h-[calc(100vh-320px)] min-h-[300px] max-h-[600px]" ref={scrollAreaRef}>
            <div className="p-4 space-y-3">
              {messages.length === 0 && (
                <div className="text-center py-8">
                  <MessageSquare className="w-10 h-10 text-muted-foreground/40 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">No messages yet. Start the conversation!</p>
                </div>
              )}

              {messages.map((msg) => {
                const isOwn = msg.sender === user?.id;
                const sender = participants.find((p) => p.id === msg.sender);

                return (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={cn('flex gap-2', isOwn ? 'justify-end' : 'justify-start')}
                  >
                    {!isOwn && (
                      <Avatar className="w-8 h-8 flex-shrink-0 mt-1">
                        <AvatarImage
                          src={sender?.avatar || undefined}
                          alt={sender?.username || ''}
                        />
                        <AvatarFallback className="bg-primary/10 text-primary text-xs">
                          {getInitials(
                            sender?.first_name && sender?.last_name
                              ? `${sender.first_name} ${sender.last_name}`
                              : sender?.username || 'U'
                          )}
                        </AvatarFallback>
                      </Avatar>
                    )}

                    <div className={cn('max-w-[75%] sm:max-w-[60%] space-y-1', isOwn ? 'items-end' : 'items-start')}>
                      {/* Sender name */}
                      {!isOwn && (
                        <p className="text-xs text-muted-foreground px-1">
                          {sender?.first_name && sender?.last_name
                            ? `${sender.first_name} ${sender.last_name}`
                            : sender?.username || 'Unknown'}
                        </p>
                      )}

                      {/* Message bubble */}
                      <div
                        className={cn(
                          'px-4 py-2.5 rounded-2xl text-sm leading-relaxed',
                          isOwn
                            ? 'bg-primary text-primary-foreground rounded-br-md'
                            : 'bg-muted text-foreground rounded-bl-md'
                        )}
                      >
                        {msg.content}
                      </div>

                      {/* Timestamp & attachment */}
                      <div className="flex items-center gap-2 px-1">
                        <span className="text-[11px] text-muted-foreground">
                          {getRelativeTime(msg.created_at)}
                        </span>
                        {msg.attachment && (
                          <span className="flex items-center gap-0.5 text-[11px] text-muted-foreground">
                            <FileText className="w-3 h-3" />
                            Attachment
                          </span>
                        )}
                        {isOwn && (
                          <span className={cn(
                            'text-[11px]',
                            msg.read ? 'text-emerald-500' : 'text-muted-foreground'
                          )}>
                            {msg.read ? 'Read' : 'Sent'}
                          </span>
                        )}
                      </div>
                    </div>
                  </motion.div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>

          {/* Message Input */}
          <Separator />
          <div className="p-3 sm:p-4">
            <div className="flex items-end gap-2">
              <Input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message..."
                className="flex-1 rounded-xl resize-none"
                disabled={sendingMessage}
              />
              <Button
                size="icon"
                className="h-10 w-10 rounded-xl flex-shrink-0 bg-emerald-600 hover:bg-emerald-700 text-white"
                onClick={handleSend}
                disabled={!newMessage.trim() || sendingMessage}
              >
                {sendingMessage ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </Button>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

// ── Main Messages Page ──────────────────────────────────────────────────────

export function MessagesPage() {
  const { navigate, currentView } = useUIStore();
  const { isAuthenticated } = useAuthStore();

  useEffect(() => {
    if (!isAuthenticated) {
      navigate({ view: 'login' });
    }
  }, [isAuthenticated, navigate]);

  if (!isAuthenticated) return null;

  // Dual view: inbox or conversation thread
  if (currentView.view === 'conversation' && currentView.id) {
    return <ConversationThread conversationId={currentView.id} />;
  }

  return <InboxView />;
}
