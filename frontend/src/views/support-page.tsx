'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback, useRef } from 'react';
import { motion } from 'framer-motion';
import {
  Headphones,
  Send,
  Paperclip,
  X,
  FileText,
  Upload,
  Loader2,
  ChevronDown,
  ChevronUp,
  Clock,
  MessageSquare,
  CheckCircle2,
  AlertCircle,
  Loader2 as Loader2Icon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { EmptyState } from '@/components/smartdalali/empty-state';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { getRelativeTime } from '@/lib/helpers';
import { toast } from 'sonner';
import type { SupportRequest } from '@/types/api';
import { cn } from '@/lib/utils';

// ── Status config ───────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<SupportRequest['status'], { label: string; variant: string; className: string }> = {
  open: {
    label: 'Open',
    variant: 'secondary',
    className: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  },
  in_progress: {
    label: 'In Progress',
    variant: 'secondary',
    className: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  },
  resolved: {
    label: 'Resolved',
    variant: 'secondary',
    className: 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400',
  },
  closed: {
    label: 'Closed',
    variant: 'secondary',
    className: 'bg-gray-100 text-gray-600 dark:bg-gray-800/30 dark:text-gray-500',
  },
};

const PRIORITY_CONFIG: Record<SupportRequest['priority'], { label: string; className: string }> = {
  low: { label: 'Low', className: 'bg-gray-100 text-gray-600 dark:bg-gray-800/30 dark:text-gray-400' },
  medium: { label: 'Medium', className: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' },
  high: { label: 'High', className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
};

// ── Support Request Card ────────────────────────────────────────────────────

function SupportRequestCard({ request }: { request: SupportRequest }) {
  const [expanded, setExpanded] = useState(false);
  const statusCfg = STATUS_CONFIG[request.status];
  const priorityCfg = PRIORITY_CONFIG[request.priority];

  return (
    <Card className="overflow-hidden">
      <CardContent className="p-0">
        <div
          className="flex items-start gap-3 p-4 cursor-pointer hover:bg-muted/30 transition-colors"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2 mb-1">
              <h3 className="text-sm font-semibold text-foreground truncate">
                {request.subject}
              </h3>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <Badge variant="secondary" className={cn('text-xs font-medium', statusCfg.className)}>
                  {statusCfg.label}
                </Badge>
                {expanded ? (
                  <ChevronUp className="w-4 h-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Clock className="w-3 h-3" />
              <span>{getRelativeTime(request.created_at)}</span>
              <span>•</span>
              <Badge variant="secondary" className={cn('text-[10px] px-1.5 py-0', priorityCfg.className)}>
                {priorityCfg.label}
              </Badge>
              {request.attachments && request.attachments.length > 0 && (
                <>
                  <span>•</span>
                  <span className="flex items-center gap-0.5">
                    <Paperclip className="w-3 h-3" />
                    {request.attachments.length}
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        {expanded && (
          <>
            <Separator />
            <div className="p-4">
              <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                {request.message}
              </p>
              {request.attachments && request.attachments.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {request.attachments.map((attachment, idx) => (
                    <a
                      key={idx}
                      href={attachment}
                      target="_blank"
                      rel="noopener noreferrer"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 text-xs text-primary hover:underline px-2 py-1 rounded-md bg-primary/5"
                    >
                      <FileText className="w-3 h-3" />
                      Attachment {idx + 1}
                    </a>
                  ))}
                </div>
              )}
              {request.updated_at !== request.created_at && (
                <p className="text-xs text-muted-foreground mt-3">
                  Last updated: {getRelativeTime(request.updated_at)}
                </p>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ── Main Support Page ───────────────────────────────────────────────────────

export function SupportPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  const [requests, setRequests] = useState<SupportRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [attachments, setAttachments] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchRequests = useCallback(async () => {
    if (!isAuthenticated) {
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const res = await api.communications.supportRequests({ page: 1, page_size: 20 });
      setRequests(res.results || []);
    } catch {
      toast.error('Failed to load support requests');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  const handleSubmit = async () => {
    if (!subject.trim() || !message.trim()) {
      toast.error('Please fill in the subject and message');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.communications.createSupportRequest({
        subject: subject.trim(),
        message: message.trim(),
        attachments: attachments.length > 0 ? attachments : undefined,
      });
      toast.success('Support request submitted successfully');
      setSubject('');
      setMessage('');
      setAttachments([]);
      fetchRequests();
    } catch {
      toast.error('Failed to submit support request');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      setAttachments((prev) => [...prev, ...newFiles].slice(0, 5));
      e.target.value = '';
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files) {
      const newFiles = Array.from(e.dataTransfer.files);
      setAttachments((prev) => [...prev, ...newFiles].slice(0, 5));
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Skeleton className="h-8 w-40 mb-6" />
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          <div className="lg:col-span-3">
            <Skeleton className="h-[400px] rounded-xl" />
          </div>
          <div className="lg:col-span-2">
            <Skeleton className="h-[300px] rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <EmptyState
          icon={Headphones}
          title="Please login to contact support"
          description="You need to be logged in to submit a support request."
          actionLabel="Login"
          onAction={() => router.push(routes.login())}
        />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-6">
          Contact Support
        </h1>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* New Request Form */}
          <div className="lg:col-span-3">
            <Card className="border-0 shadow-lg shadow-black/5">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Headphones className="w-5 h-5 text-emerald-600" />
                  New Support Request
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Subject */}
                <div className="space-y-2">
                  <Label htmlFor="subject" className="text-sm font-medium">
                    Subject
                  </Label>
                  <Input
                    id="subject"
                    placeholder="Brief description of your issue"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    className="h-10"
                  />
                </div>

                {/* Message */}
                <div className="space-y-2">
                  <Label htmlFor="message" className="text-sm font-medium">
                    Message
                  </Label>
                  <Textarea
                    id="message"
                    placeholder="Describe your issue in detail..."
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    className="min-h-[120px] resize-none"
                  />
                </div>

                {/* File Upload */}
                <div className="space-y-2">
                  <Label className="text-sm font-medium">Attachments</Label>
                  <div
                    className={cn(
                      'border-2 border-dashed rounded-xl p-4 text-center transition-colors cursor-pointer',
                      isDragging
                        ? 'border-emerald-500 bg-emerald-50 dark:bg-emerald-950/20'
                        : 'border-muted-foreground/25 hover:border-muted-foreground/40'
                    )}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">
                      Drag & drop files here, or <span className="text-primary font-medium">browse</span>
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Up to 5 files, max 10MB each
                    </p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      className="hidden"
                      onChange={handleFileChange}
                      accept="image/*,.pdf,.doc,.docx,.txt"
                    />
                  </div>

                  {/* Attached files list */}
                  {attachments.length > 0 && (
                    <div className="space-y-2">
                      {attachments.map((file, idx) => (
                        <div
                          key={`${file.name}-${idx}`}
                          className="flex items-center gap-2 px-3 py-2 bg-muted rounded-lg"
                        >
                          <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                          <span className="text-sm text-foreground truncate flex-1">
                            {file.name}
                          </span>
                          <span className="text-xs text-muted-foreground flex-shrink-0">
                            {(file.size / 1024).toFixed(0)} KB
                          </span>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6 flex-shrink-0"
                            onClick={() => removeAttachment(idx)}
                          >
                            <X className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Submit */}
                <Button
                  className="w-full gap-2 rounded-xl h-11"
                  onClick={handleSubmit}
                  disabled={isSubmitting || !subject.trim() || !message.trim()}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Submitting...
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      Submit Request
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Previous Requests */}
          <div className="lg:col-span-2">
            <Card className="border-0 shadow-lg shadow-black/5">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg flex items-center justify-between">
                  <span>Previous Requests</span>
                  <span className="text-sm font-normal text-muted-foreground">
                    {requests.length}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {requests.length === 0 ? (
                  <div className="text-center py-6">
                    <MessageSquare className="w-8 h-8 text-muted-foreground/40 mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">
                      No previous support requests
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
                    {requests.map((request) => (
                      <SupportRequestCard key={request.id} request={request} />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
