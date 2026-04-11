'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { useAuthStore } from '@/store';
import { canAccessSellerPortal } from '@/lib/auth-roles';
import { api } from '@/lib/api-client';
import { Store, Loader2, ArrowRight } from 'lucide-react';

export function SellerRegisterPage() {
  const router = useRouter();
  const { user, isAuthenticated, setUser } = useAuthStore();
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push(routes.login());
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (user && canAccessSellerPortal(user)) {
      toast.info('You are already registered as a seller!');
      router.push(routes.sellerDashboard());
    }
  }, [user, router]);

  const onBecomeSeller = async () => {
    if (!user) return;
    setIsLoading(true);
    try {
      // Backend "become seller" upgrades the role and returns fresh JWTs.
      const res = await api.auth.becomeSeller();
      api.setTokens(res.access, res.refresh);

      const me = await api.auth.me();
      setUser(me as any);
      
      toast.success('Awesome! Let\'s setup your store.');
      router.push(routes.sellerOnboardingStoreSetup());
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to register as seller.';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isAuthenticated || !user) return null;

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4">
      <div className="max-w-md text-center space-y-8">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex justify-center">
          <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center">
            <Store className="w-10 h-10 text-primary" />
          </div>
        </motion.div>
        
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>
          <h1 className="text-3xl font-bold mb-4 text-foreground">Ready to start selling?</h1>
          <p className="text-muted-foreground">
            Join SmartDalali and reach millions of buyers across Tanzania. 
            It only takes 2 minutes to get started!
          </p>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <Button onClick={onBecomeSeller} disabled={isLoading} className="w-full h-14 text-lg">
            {isLoading ? <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> Upgrading account...</> : <>Become a Seller <ArrowRight className="ml-2 w-5 h-5" /></>}
          </Button>
        </motion.div>
      </div>
    </div>
  );
}
