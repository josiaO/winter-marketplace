'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Star } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { api } from '@/lib/api-client';
import { routes } from '@/lib/routes';
import { useAuthStore } from '@/store';
import { canAccessSellerPortal } from '@/lib/auth-roles';
import { useRouter } from 'next/navigation';
import type { Review, PaginatedResponse } from '@/types/api';
import { getRelativeTime } from '@/lib/helpers';
import Link from 'next/link';

export function SellerReviewsPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated || !user || !canAccessSellerPortal(user)) {
      router.push(routes.login());
      return;
    }
    void (async () => {
      try {
        const res = await api.trust.reviews({});
        const rows = (res as PaginatedResponse<Review>).results ?? [];
        setReviews(rows);
      } catch {
        toast.error('Could not load reviews.');
      } finally {
        setLoading(false);
      }
    })();
  }, [isAuthenticated, user, router]);

  if (!isAuthenticated || !user) return null;

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Star className="w-7 h-7 text-amber-500" />
          Reviews
        </h1>
        <p className="text-muted-foreground mt-1">What buyers say after their order.</p>
      </motion.div>

      {loading ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : reviews.length === 0 ? (
        <p className="text-sm text-muted-foreground">No reviews yet. Great service earns stars here.</p>
      ) : (
        <div className="space-y-3">
          {reviews.map((r) => {
            const lid = typeof r.listing === 'object' ? r.listing.id : r.listing;
            const name =
              [r.reviewer?.first_name, r.reviewer?.last_name].filter(Boolean).join(' ') || r.reviewer?.username;
            return (
              <Card key={r.id} className="border-0 shadow-md">
                <CardContent className="p-4 space-y-2">
                  <div className="flex justify-between gap-2">
                    <p className="font-medium">{name}</p>
                    <span className="text-amber-600 text-sm font-semibold">{r.rating}/5</span>
                  </div>
                  {r.comment && <p className="text-sm text-muted-foreground">{r.comment}</p>}
                  <p className="text-xs text-muted-foreground">{getRelativeTime(r.created_at)}</p>
                  {lid != null && (
                    <Link href={routes.sellerListingEdit(String(lid))} className="text-xs text-primary hover:underline">
                      View listing
                    </Link>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
