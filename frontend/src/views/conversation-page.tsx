'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  Send,
  FileText,
  Image as ImageIcon,
  Paperclip,
  Package,
  Loader2,
  MessageSquare,
  X,
  ShoppingBag,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { EmptyState } from '@/components/smartdalali/empty-state';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { getRelativeTime, getInitials } from '@/lib/helpers';
import { toast } from 'sonner';
import type { Message, ConversationParticipant, Listing, Order } from '@/types/api';
import { cn } from '@/lib/utils';

// ── Conversation Page ───────────────────────────────────────────────────────

export function ConversationPage({ conversationId }: { conversationId: string }) {
  const router = useRouter();
  const { isAuthenticated, user } = useAuthStore();

  const [messages, setMessages] = useState<Message[]>([]);
  const [participants, setParticipants] = useState<ConversationParticipant[]>([]);
  const [listing, setListing] = useState<Listing | null>(null);
  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [newMessage, setNewMessage] = useState('');
  const [attachment, setAttachment] = useState<File | null>(null);
  const [isOtherTyping, setIsOtherTyping] = useState(false);
  const [otherOnlineStatus, setOtherOnlineStatus] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      if (scrollAreaRef.current) {
        const viewport = scrollAreaRef.current.querySelector('[data-radix-scroll-area-viewport]');
        if (viewport) {
          viewport.scrollTop = viewport.scrollHeight;
        }
      }
    }, 50);
  }, []);

  const fetchConversation = useCallback(async () => {
    if (!isAuthenticated || !conversationId) return;
    setIsLoading(true);
    try {
      // Fetch messages
      const msgRes = await api.communications.messages(conversationId, {
        page: 1,
        page_size: 100,
      });
      setMessages(msgRes?.results || []);

      // Fetch conversation details
      const convRes = await api.communications.conversations();
      const conv = convRes.results?.find((c) => String(c.id) === String(conversationId));
      if (conv) {
        setParticipants(conv.participants || []);
        setListing((conv.listing as Listing) || null);
        setOrder((conv.order as Order) || null);
      }

      // Mark as read
      await api.communications.markRead(conversationId).catch(() => {});
    } catch {
      toast.error('Failed to load conversation');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, conversationId]);

  useEffect(() => {
    fetchConversation();
    
    // Connect to WebSocket for real-time updates
    if (isAuthenticated && conversationId) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      // Use token for auth — the JWTAuthMiddleware in backend handles this
      const token = useAuthStore.getState().token;
      const wsUrl = `${protocol}//${host}/ws/chat/${conversationId}/?token=${token}`;
      
      const socket = new WebSocket(wsUrl);
      socketRef.current = socket;

      socket.onopen = () => {
        console.log('Chat WebSocket connected');
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'message') {
            setMessages((prev) => {
              // Avoid duplicates
              if (prev.some(m => m.id === data.message.id)) return prev;
              return [...prev, data.message];
            });
            // Mark as read locally if we're active
            if (document.visibilityState === 'visible') {
              api.communications.markRead(conversationId).catch(() => {});
            }
          } else if (data.type === 'typing') {
            setIsOtherTyping(data.is_typing);
            // Auto-clear typing after 3s if no new typing event
            if (data.is_typing) {
              if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
              typingTimeoutRef.current = setTimeout(() => setIsOtherTyping(false), 3000);
            }
          } else if (data.type === 'user_status') {
            setOtherOnlineStatus(data.is_online);
          }
        } catch (err) {
          console.error('WS Message parsing error:', err);
        }
      };

      socket.onclose = () => {
        console.log('Chat WebSocket disconnected');
      };

      return () => {
        socket.close();
        if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
      };
    }
  }, [fetchConversation, isAuthenticated, conversationId]);

  // Handle outgoing typing indicator
  useEffect(() => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      const isTyping = newMessage.length > 0;
      socketRef.current.send(JSON.stringify({
        type: 'typing',
        is_typing: isTyping
      }));
    }
  }, [newMessage]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSend = async () => {
    if ((!newMessage.trim() && !attachment) || sendingMessage) return;

    setSendingMessage(true);
    const content = newMessage.trim();
    setNewMessage('');
    setAttachment(null);

    try {
      const sent = await api.communications.sendMessage(conversationId!, {
        text: content,
        attachment: attachment || undefined,
      });
      // WebSocket will also broadcast this, but updating locally for instant feedback
      setMessages((prev) => {
        if (prev.some(m => m.id === sent.id)) return prev;
        return [...prev, sent];
      });
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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setAttachment(e.target.files[0]);
      e.target.value = '';
    }
  };

  const otherParticipant =
    participants.find((p) => p.id !== user?.id) || participants[0];

  if (!isAuthenticated) {
    router.push(routes.login());
    return null;
  }

  if (!conversationId) {
    router.push(routes.messages());
    return null;
  }

  // ── Loading state ────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-8 w-40 mb-6" />
        <div className="rounded-xl border overflow-hidden">
          {/* Header skeleton */}
          <div className="p-4 border-b flex items-center gap-3">
            <Skeleton className="w-10 h-10 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-48" />
            </div>
          </div>
          {/* Messages skeleton */}
          <div className="p-4 space-y-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className={cn(
                  'flex gap-2',
                  i % 2 === 0 ? 'justify-start' : 'justify-end'
                )}
              >
                {i % 2 === 0 && <Skeleton className="w-8 h-8 rounded-full" />}
                <Skeleton
                  className={cn(
                    'h-16 rounded-2xl',
                    i % 2 === 0 ? 'w-56' : 'w-48 bg-primary/10'
                  )}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const participantName = otherParticipant
    ? otherParticipant.first_name && otherParticipant.last_name
      ? `${otherParticipant.first_name} ${otherParticipant.last_name}`
      : otherParticipant.username
    : 'Unknown User';

  const participantInitials = getInitials(
    otherParticipant
      ? otherParticipant.first_name && otherParticipant.last_name
        ? `${otherParticipant.first_name} ${otherParticipant.last_name}`
        : otherParticipant.username || 'U'
      : 'U'
  );

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        {/* ── Conversation Header ───────────────────────────────────────── */}
        <div className="rounded-xl border bg-card overflow-hidden shadow-sm">
          {/* Top bar */}
          <div className="p-3 sm:p-4 border-b">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 rounded-full flex-shrink-0"
                onClick={() => router.push(routes.messages())}
              >
                <ArrowLeft className="w-4 h-4" />
              </Button>

              <Avatar className="w-10 h-10 flex-shrink-0">
                <AvatarImage
                  src={otherParticipant?.avatar || undefined}
                  alt={participantName}
                />
                <AvatarFallback className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 text-sm font-semibold">
                  {participantInitials}
                </AvatarFallback>
              </Avatar>

              <div className="flex-1 min-w-0">
                <h1 className="text-base sm:text-lg font-semibold text-foreground truncate">
                  {participantName}
                </h1>
                <div className="flex items-center gap-2 mt-0.5">
                  <div className="flex items-center gap-1">
                    <div className={cn(
                      "w-2 h-2 rounded-full",
                      otherOnlineStatus ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-gray-300 dark:bg-gray-600"
                    )} />
                    <span className="text-[10px] sm:text-xs text-muted-foreground">
                      {isOtherTyping ? (
                        <span className="text-emerald-600 dark:text-emerald-400 font-medium animate-pulse">
                          Typing...
                        </span>
                      ) : (
                        otherOnlineStatus ? "Online" : "Offline"
                      )}
                    </span>
                  </div>
                  <span className="text-muted-foreground/30 text-xs">•</span>
                  {listing && (
                    <span className="flex items-center gap-1 text-[10px] sm:text-xs text-muted-foreground truncate max-w-[120px] sm:max-w-none">
                      <Package className="w-3 h-3 flex-shrink-0" />
                      Re: {listing.title}
                    </span>
                  )}
                  {order && (
                    <span className="flex items-center gap-1 text-[10px] sm:text-xs text-muted-foreground">
                      <ShoppingBag className="w-3 h-3 flex-shrink-0" />
                      #{order.order_number}
                    </span>
                  )}
                </div>
              </div>

              {/* Context buttons */}
              {listing && (
                <Button
                  variant="outline"
                  size="sm"
                  className="hidden sm:flex gap-1.5 rounded-full text-xs"
                  onClick={() => router.push(routes.product(String(listing.id)))}
                >
                  <Package className="w-3.5 h-3.5" />
                  View Listing
                </Button>
              )}
            </div>
          </div>

          {/* ── Messages ─────────────────────────────────────────────────── */}
          <ScrollArea
            className="h-[calc(100vh-340px)] min-h-[300px] max-h-[600px]"
            ref={scrollAreaRef}
          >
            <div className="p-4 space-y-3">
              {messages.length === 0 && (
                <div className="text-center py-12">
                  <MessageSquare className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
                  <p className="text-sm font-medium text-foreground mb-1">
                    No messages yet
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Send a message to start the conversation
                  </p>
                </div>
              )}

              {messages.map((msg, idx) => {
                const isOwn = msg.sender === user?.id;
                const sender = participants.find((p) => p.id === msg.sender);
                const showAvatar =
                  !isOwn &&
                  (idx === 0 || messages[idx - 1]?.sender !== msg.sender);

                return (
                  <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={cn('flex gap-2', isOwn ? 'justify-end' : 'justify-start')}
                  >
                    {/* Avatar for other person */}
                    {!isOwn && (
                      <div className="w-8 flex-shrink-0">
                        {showAvatar && (
                          <Avatar className="w-8 h-8">
                            <AvatarImage
                              src={sender?.avatar || undefined}
                              alt={sender?.username || ''}
                            />
                            <AvatarFallback className="bg-primary/10 text-primary text-[10px]">
                              {getInitials(
                                sender?.first_name && sender?.last_name
                                  ? `${sender.first_name} ${sender.last_name}`
                                  : sender?.username || 'U'
                              )}
                            </AvatarFallback>
                          </Avatar>
                        )}
                      </div>
                    )}

                    <div
                      className={cn(
                        'max-w-[75%] sm:max-w-[65%] space-y-0.5',
                        isOwn ? 'items-end' : 'items-start'
                      )}
                    >
                      {/* Sender name */}
                      {!isOwn && showAvatar && (
                        <p className="text-[11px] text-muted-foreground px-1">
                          {sender?.first_name && sender?.last_name
                            ? `${sender.first_name} ${sender.last_name}`
                            : sender?.username || 'Unknown'}
                        </p>
                      )}

                      {/* Message bubble */}
                      <div
                        className={cn(
                          'px-3.5 py-2.5 text-sm leading-relaxed break-words',
                          isOwn
                            ? 'bg-emerald-600 text-white rounded-2xl rounded-br-md'
                            : 'bg-muted text-foreground rounded-2xl rounded-bl-md'
                        )}
                      >
                        {msg.content}
                      </div>

                      {/* Timestamp + read status */}
                      <div className="flex items-center gap-1.5 px-1">
                        <span className="text-[10px] text-muted-foreground">
                          {getRelativeTime(msg.created_at)}
                        </span>
                        {msg.attachment && (
                          <a
                            href={msg.attachment}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-0.5 text-[10px] text-primary hover:underline"
                          >
                            <Paperclip className="w-2.5 h-2.5" />
                            View
                          </a>
                        )}
                        {isOwn && (
                          <span
                            className={cn(
                              'text-[10px]',
                              msg.read
                                ? 'text-emerald-500'
                                : 'text-muted-foreground'
                            )}
                          >
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

          {/* ── Message Input ────────────────────────────────────────────── */}
          <Separator />

          {/* Attachment preview */}
          <AnimatePresence>
            {attachment && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="px-3 sm:px-4 pt-3"
              >
                <div className="flex items-center gap-2 px-3 py-2 bg-muted rounded-lg">
                  <Paperclip className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  <span className="text-sm text-foreground truncate flex-1">
                    {attachment.name}
                  </span>
                  <span className="text-xs text-muted-foreground flex-shrink-0">
                    {(attachment.size / 1024).toFixed(0)} KB
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 flex-shrink-0"
                    onClick={() => setAttachment(null)}
                  >
                    <X className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="p-3 sm:p-4">
            <div className="flex items-end gap-2">
              {/* Attachment button */}
              <Button
                variant="ghost"
                size="icon"
                className="h-10 w-10 rounded-xl flex-shrink-0 text-muted-foreground hover:text-foreground"
                onClick={() => fileInputRef.current?.click()}
              >
                <Paperclip className="w-4 h-4" />
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  onChange={handleFileChange}
                  accept="image/*,.pdf,.doc,.docx,.txt"
                />
              </Button>

              {/* Text input */}
              <Input
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type a message..."
                className="flex-1 rounded-xl h-10"
                disabled={sendingMessage}
              />

              {/* Send button */}
              <Button
                size="icon"
                className={cn(
                  'h-10 w-10 rounded-xl flex-shrink-0 transition-colors',
                  newMessage.trim() || attachment
                    ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                    : 'bg-muted text-muted-foreground'
                )}
                onClick={handleSend}
                disabled={(!newMessage.trim() && !attachment) || sendingMessage}
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
