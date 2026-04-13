'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { ApiClientError } from '@/types/api';
import {
  Smartphone, Shirt, Home, Coffee, CarFront, BookOpen,
  Sparkles, Dumbbell, PackageSearch, Loader2, Store,
  ShoppingBag, Wrench
} from 'lucide-react';

interface StoreSetupFormValues {
  store_name: string;
  store_category: string;
  store_category_other?: string;
  store_location: string;
  seller_type: 'product' | 'service';
}

const CATEGORIES = [
  { id: 'electronics', label: 'Electronics', icon: Smartphone },
  { id: 'fashion', label: 'Fashion', icon: Shirt },
  { id: 'home', label: 'Home Goods', icon: Home },
  { id: 'food', label: 'Food & Groceries', icon: Coffee },
  { id: 'auto_parts', label: 'Auto Parts', icon: CarFront },
  { id: 'books', label: 'Books', icon: BookOpen },
  { id: 'beauty', label: 'Beauty & Health', icon: Sparkles },
  { id: 'sports', label: 'Sports', icon: Dumbbell },
  { id: 'other', label: 'Other', icon: PackageSearch },
];

const REGIONS = [
  'Arusha', 'Dar es Salaam', 'Dodoma', 'Geita', 'Iringa', 'Kagera',
  'Katavi', 'Kigoma', 'Kilimanjaro', 'Lindi', 'Manyara', 'Mara',
  'Mbeya', 'Morogoro', 'Mtwara', 'Mwanza', 'Njombe', 'Pemba Kaskazini',
  'Pemba Kusini', 'Pwani', 'Rukwa', 'Ruvuma', 'Shinyanga', 'Simiyu',
  'Singida', 'Songwe', 'Tabora', 'Tanga', 'Unguja Kaskazini',
  'Unguja Kusini', 'Unguja Mjini Magharibi'
];

export function SellerStoreSetupPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('');
  const [sellerType, setSellerType] = useState<'product' | 'service'>('product');

  const { register, handleSubmit, setValue, formState: { errors } } = useForm<StoreSetupFormValues>({
    defaultValues: { store_name: '', store_category: '', store_category_other: '', store_location: '', seller_type: 'product' }
  });

  useEffect(() => {
    if (!isAuthenticated) router.push(routes.login());
  }, [isAuthenticated, router]);

  const selectCategory = (id: string) => {
    setSelectedCategory(id);
    setValue('store_category', id, { shouldValidate: true });
  };

  const selectSellerType = (type: 'product' | 'service') => {
    setSellerType(type);
    setValue('seller_type', type);
  };

  const onSubmit = async (data: StoreSetupFormValues) => {
    if (!data.store_category) {
      toast.error('Tafadhali chagua aina ya biashara yako. (Please select a category)');
      return;
    }
    if (!data.store_location) {
      toast.error('Tafadhali chagua mkoa uliopo. (Please select a location)');
      return;
    }
    if (data.store_category === 'other' && !data.store_category_other?.trim()) {
      toast.error('Please describe your store category when selecting Other.');
      return;
    }

    setIsLoading(true);
    try {
      await api.sellers.storeSetup({
        store_name: data.store_name,
        store_category: data.store_category,
        store_category_other: data.store_category === 'other' ? data.store_category_other?.trim() : '',
        store_location: data.store_location,
        seller_type: data.seller_type,
      } as any);
      toast.success('Duka lako limeundwa! Anza kuongeza bidhaa.');
      router.push(routes.sellerDashboard());
    } catch (err: unknown) {
      if (err instanceof ApiClientError) {
        const firstFieldError = Object.values(err.errors || {})[0]?.[0];
        toast.error(firstFieldError || err.detail || err.message || 'Failed to setup store.');
      } else {
        toast.error(err instanceof Error ? err.message : 'Failed to setup store.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (!isAuthenticated || !user) return null;

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-primary/10 rounded-2xl mb-4 text-primary">
            <Store className="w-8 h-8" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold mb-2 text-foreground">Welcome, Seller!</h1>
          <p className="text-muted-foreground">Let&apos;s get your store set up so you can start selling.</p>
        </motion.div>

        <motion.form onSubmit={handleSubmit(onSubmit)} className="space-y-8" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}>

          {/* Store Name */}
          <div className="space-y-3">
            <Label htmlFor="store_name" className="text-base font-semibold">What is your store called?</Label>
            <Input
              id="store_name"
              placeholder="e.g. Duka la Amina"
              className="h-12 text-lg"
              {...register('store_name', { required: 'Store name is required' })}
            />
            {errors.store_name && <p className="text-sm text-destructive">{errors.store_name.message}</p>}
          </div>

          {/* Seller Type — Product or Service */}
          <div className="space-y-3">
            <Label className="text-base font-semibold">What are you selling?</Label>
            <p className="text-xs text-muted-foreground -mt-1">This helps buyers find you in the right category.</p>
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => selectSellerType('product')}
                className={`flex flex-col items-center justify-center gap-3 p-5 rounded-2xl border-2 transition-all ${
                  sellerType === 'product'
                    ? 'border-primary bg-primary/5 text-primary ring-2 ring-primary/20'
                    : 'border-muted bg-card hover:border-primary/40 text-muted-foreground'
                }`}
              >
                <ShoppingBag className="w-8 h-8" />
                <div>
                  <p className="font-semibold text-sm">Physical / Digital Product</p>
                  <p className="text-xs opacity-70 mt-0.5">Goods you ship or deliver</p>
                </div>
              </button>
              <button
                type="button"
                onClick={() => selectSellerType('service')}
                className={`flex flex-col items-center justify-center gap-3 p-5 rounded-2xl border-2 transition-all ${
                  sellerType === 'service'
                    ? 'border-primary bg-primary/5 text-primary ring-2 ring-primary/20'
                    : 'border-muted bg-card hover:border-primary/40 text-muted-foreground'
                }`}
              >
                <Wrench className="w-8 h-8" />
                <div>
                  <p className="font-semibold text-sm">Service</p>
                  <p className="text-xs opacity-70 mt-0.5">Skills, repairs, consultations</p>
                </div>
              </button>
            </div>
          </div>

          {/* Category */}
          <div className="space-y-3">
            <Label className="text-base font-semibold">Which category best describes you?</Label>
            <div className="grid grid-cols-3 gap-3">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => selectCategory(cat.id)}
                  className={`flex flex-col items-center justify-center gap-2 p-4 rounded-xl border-2 transition-all ${
                    selectedCategory === cat.id
                      ? 'border-primary bg-primary/5 text-primary'
                      : 'border-muted bg-card hover:border-primary/50 text-muted-foreground hover:text-foreground'
                  }`}
                >
                  <cat.icon className="w-6 h-6" />
                  <span className="text-xs font-medium text-center leading-tight">{cat.label}</span>
                </button>
              ))}
            </div>
            {selectedCategory === 'other' && (
              <div className="space-y-2">
                <Label htmlFor="store_category_other" className="text-sm font-medium">
                  Tell us what you sell
                </Label>
                <Input
                  id="store_category_other"
                  placeholder="e.g. Handmade crafts, farm supplies..."
                  className="h-11"
                  {...register('store_category_other', {
                    validate: (value) =>
                      selectedCategory !== 'other' || !!value?.trim() || 'Please describe your category',
                  })}
                />
                {errors.store_category_other && (
                  <p className="text-sm text-destructive">{errors.store_category_other.message}</p>
                )}
              </div>
            )}
          </div>

          {/* Location */}
          <div className="space-y-3">
            <Label className="text-base font-semibold">Where are you based?</Label>
            <Select onValueChange={(v) => setValue('store_location', v)}>
              <SelectTrigger className="h-12 text-lg">
                <SelectValue placeholder="Select your region" />
              </SelectTrigger>
              <SelectContent className="max-h-[300px]">
                {REGIONS.map(r => (
                  <SelectItem key={r} value={r}>{r}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <p className="text-sm text-center text-muted-foreground pt-2">
            You can change these details later from your settings.
          </p>

          <Button type="submit" disabled={isLoading} className="w-full h-14 text-lg">
            {isLoading ? <><Loader2 className="w-5 h-5 animate-spin mr-2"/>Setting up...</> : 'Tengeneza Duka Langu →'}
          </Button>
        </motion.form>
      </div>
    </div>
  );
}
