'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import {
  Store,
  MapPin,
  FileText,
  Bell,
  Save,
  Loader2,
  Camera,
  Image as ImageIcon,
  User,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { api } from '@/lib/api-client';
import { useAuthStore } from '@/store';
import { routes } from '@/lib/routes';
import { ApiClientError } from '@/types/api';

// ─── Schema ────────────────────────────────────────────────────────────────────

const settingsSchema = z.object({
  store_name: z.string().min(3, 'Store name must be at least 3 characters').max(100),
  store_description: z.string().max(2000).optional(),
  store_location: z.string().min(2, 'Location is required').max(100),
  business_email: z.string().email('Invalid email').optional().or(z.literal('')),
  business_phone: z.string().max(20).optional().or(z.literal('')),
  business_address: z.string().max(500).optional().or(z.literal('')),
  notification_orders: z.boolean().default(true),
  notification_messages: z.boolean().default(true),
  notification_reviews: z.boolean().default(true),
});

type SettingsFormData = z.infer<typeof settingsSchema>;

// ─── Sub-component: Image Upload Field ─────────────────────────────────────────

interface ImageUploadFieldProps {
  label: string;
  description?: string;
  currentValue?: string | null;
  onFileSelect: (file: File) => void;
  aspect?: 'square' | 'video';
}

function ImageUploadField({ label, description, currentValue, onFileSelect, aspect = 'square' }: ImageUploadFieldProps) {
  const [preview, setPreview] = useState<string | null>(currentValue || null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        toast.error('Please select an image file.');
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        toast.error('Image must be under 5MB.');
        return;
      }
      onFileSelect(file);
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target?.result as string);
      reader.readAsDataURL(file);
    }
  };

  return (
    <div className="space-y-3">
      <Label>{label}</Label>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
      <div 
        onClick={() => fileInputRef.current?.click()}
        className={cn(
          "relative group cursor-pointer border-2 border-dashed rounded-xl overflow-hidden flex items-center justify-center bg-muted/30 hover:bg-muted/50 transition-all",
          aspect === 'square' ? "w-32 h-32" : "w-full aspect-[3/1]"
        )}
      >
        {preview ? (
          <>
            <img src={preview} alt={label} className="w-full h-full object-cover" />
            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
              <Camera className="w-8 h-8 text-white" />
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center gap-2 text-muted-foreground group-hover:text-primary transition-colors">
            <ImageIcon className="w-8 h-8" />
            <span className="text-xs font-medium">Click to upload</span>
          </div>
        )}
        <input 
          type="file" 
          ref={fileInputRef} 
          onChange={handleFileChange} 
          accept="image/*" 
          className="hidden" 
        />
      </div>
    </div>
  );
}



// ─── Main View ─────────────────────────────────────────────────────────────────

export function SellerSettingsView() {
  const router = useRouter();
  const { user, fetchUser } = useAuthStore();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [bannerFile, setBannerFile] = useState<File | null>(null);
  const [storeCategory, setStoreCategory] = useState<string>('');
  const [storeCategoryOther, setStoreCategoryOther] = useState<string>('');

  const form = useForm<SettingsFormData>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      store_name: '',
      store_description: '',
      store_location: '',
      business_email: '',
      business_phone: '',
      business_address: '',
      notification_orders: true,
      notification_messages: true,
      notification_reviews: true,
    },
  });

  useEffect(() => {
    if (user?.seller_profile) {
        const sp = user.seller_profile;
        const existingCategory =
          ((sp as any).store_categories && Array.isArray((sp as any).store_categories) && (sp as any).store_categories[0]) ||
          (sp as any).store_category ||
          '';
        setStoreCategory(existingCategory);
        setStoreCategoryOther((sp as any).store_category_other || '');
        form.reset({
            store_name: sp.store_name || '',
            store_description: sp.store_description || '',
            store_location: sp.store_location || '',
            business_email: sp.business_email || '',
            business_phone: sp.business_phone || '',
            business_address: sp.business_address || '',
            notification_orders: sp.notification_orders ?? true,
            notification_messages: sp.notification_messages ?? true,
            notification_reviews: sp.notification_reviews ?? true,
        });
    }
  }, [user, form]);

  const onSubmit = async (data: SettingsFormData) => {
    if (!storeCategory) {
      toast.error('Please select a store category.');
      return;
    }
    if (storeCategory === 'other' && !storeCategoryOther.trim()) {
      toast.error('Please describe your category when selecting Other.');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.sellers.storeSetup({
        ...data,
        store_category: storeCategory,
        store_category_other: storeCategory === 'other' ? storeCategoryOther.trim() : '',
        store_logo: logoFile,
        store_banner: bannerFile,
      });
      toast.success('Store settings updated successfully!');
      await fetchUser(); // Refresh profile data
    } catch (err) {
      if (err instanceof ApiClientError) {
        const firstFieldError = Object.values(err.errors || {})[0]?.[0];
        toast.error(firstFieldError || err.detail || err.message || 'Failed to update settings.');
      } else {
        toast.error(err instanceof Error ? err.message : 'Failed to update settings.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!user?.is_seller) return null;

  return (
    <div className="space-y-8 pb-10">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Store Settings</h1>
          <p className="text-muted-foreground mt-1">
            Manage your store's public profile and account preferences
          </p>
        </div>
        <Button 
          onClick={form.handleSubmit(onSubmit)} 
          disabled={isSubmitting}
          className="w-full sm:w-auto gap-2"
        >
          {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save Changes
        </Button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        {/* Left Column: Profile & Branding */}
        <div className="xl:col-span-2 space-y-6">
          <Card className="overflow-hidden border-0 shadow-md shadow-black/5">
            <CardHeader className="bg-muted/30 border-b">
              <div className="flex items-center gap-2">
                <Store className="w-5 h-5 text-primary" />
                <CardTitle>Branding & Identity</CardTitle>
              </div>
              <CardDescription>
                How your store appears to customers on the marketplace
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-6 space-y-6">
               <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                 <ImageUploadField 
                   label="Store Logo"
                   description="Recommended: 512x512px square"
                   currentValue={user.seller_profile?.store_logo}
                   onFileSelect={setLogoFile}
                   aspect="square"
                 />
                 <div className="flex-1">
                    <Label className="mb-3 block">Verification Status</Label>
                    <div className="p-4 rounded-xl bg-muted/50 border flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <ShieldCheck className={cn("w-6 h-6", user.seller_profile?.verification_status === 'verified' ? "text-green-500" : "text-amber-500")} />
                            <div>
                                <p className="font-semibold capitalize">{user.seller_profile?.verification_status || 'Incomplete'}</p>
                                <p className="text-xs text-muted-foreground">Identity Verification</p>
                            </div>
                        </div>
                        <Button variant="outline" size="sm" onClick={() => router.push(routes.sellerVerification())}>
                            View Details
                        </Button>
                    </div>
                 </div>
               </div>

               <Separator />

               <ImageUploadField 
                 label="Store Banner"
                 description="Displayed on your public store page. Recommended: 1200x400px"
                 currentValue={user.seller_profile?.store_banner}
                 onFileSelect={setBannerFile}
                 aspect="video"
               />

               <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                 <div className="space-y-2">
                   <Label htmlFor="store_name">Store Name</Label>
                   <Input id="store_name" {...form.register('store_name')} />
                   {form.formState.errors.store_name && (
                     <p className="text-xs text-destructive">{form.formState.errors.store_name.message}</p>
                   )}
                 </div>
                 <div className="space-y-2">
                   <Label htmlFor="store_location">Store Location / City</Label>
                   <Input id="store_location" {...form.register('store_location')} />
                   {form.formState.errors.store_location && (
                     <p className="text-xs text-destructive">{form.formState.errors.store_location.message}</p>
                   )}
                 </div>
               </div>

               <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                 <div className="space-y-2">
                   <Label>Store Category</Label>
                   <Select
                     value={storeCategory || '__unset'}
                     onValueChange={(v) => setStoreCategory(v === '__unset' ? '' : v)}
                   >
                     <SelectTrigger>
                       <SelectValue placeholder="Select store category" />
                     </SelectTrigger>
                     <SelectContent>
                       <SelectItem value="__unset">Select store category</SelectItem>
                       <SelectItem value="electronics">Electronics</SelectItem>
                       <SelectItem value="fashion">Fashion</SelectItem>
                       <SelectItem value="home">Home</SelectItem>
                       <SelectItem value="food">Food</SelectItem>
                       <SelectItem value="auto_parts">Auto Parts</SelectItem>
                       <SelectItem value="books">Books</SelectItem>
                       <SelectItem value="beauty">Beauty</SelectItem>
                       <SelectItem value="sports">Sports</SelectItem>
                       <SelectItem value="other">Other</SelectItem>
                     </SelectContent>
                   </Select>
                 </div>
                 {storeCategory === 'other' && (
                   <div className="space-y-2">
                     <Label htmlFor="store_category_other">Other Category</Label>
                     <Input
                       id="store_category_other"
                       value={storeCategoryOther}
                       onChange={(e) => setStoreCategoryOther(e.target.value)}
                       placeholder="Describe your store category"
                     />
                   </div>
                 )}
               </div>

               <div className="space-y-2">
                 <Label htmlFor="store_description">Store Description</Label>
                 <Textarea 
                   id="store_description" 
                   rows={4} 
                   placeholder="Describe what your store offers..."
                   {...form.register('store_description')} 
                 />
                 <p className="text-[10px] text-right text-muted-foreground">
                   {(form.watch('store_description') || '').length}/2000 characters
                 </p>
               </div>
            </CardContent>
          </Card>

          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="bg-muted/30 border-b">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-primary" />
                <CardTitle>Business Information</CardTitle>
              </div>
              <CardDescription>
                Operational and contact details (only visible to buyers after purchase)
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-6 space-y-4">
               <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                 <div className="space-y-2">
                   <Label htmlFor="business_email">Customer Support Email</Label>
                   <Input id="business_email" type="email" placeholder="sales@yourstore.com" {...form.register('business_email')} />
                 </div>
                 <div className="space-y-2">
                   <Label htmlFor="business_phone">Customer Support Phone</Label>
                   <Input id="business_phone" placeholder="+255..." {...form.register('business_phone')} />
                 </div>
               </div>
               <div className="space-y-2">
                 <Label htmlFor="business_address">Physical Business Address</Label>
                 <Textarea id="business_address" rows={2} {...form.register('business_address')} />
               </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Preferences */}
        <div className="space-y-6">
          <Card className="border-0 shadow-md shadow-black/5">
            <CardHeader className="pb-4">
              <div className="flex items-center gap-2">
                <Bell className="w-5 h-5 text-primary" />
                <CardTitle className="text-lg">Notifications</CardTitle>
              </div>
              <CardDescription>
                Manage how you receive alerts
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
               <div className="flex items-center justify-between space-x-2">
                 <Label htmlFor="notify-orders" className="flex flex-col gap-0.5 cursor-pointer">
                   <span className="text-sm font-semibold">Order Alerts</span>
                   <span className="text-xs font-normal text-muted-foreground">New orders and status updates</span>
                 </Label>
                 <Switch 
                   id="notify-orders" 
                   checked={form.watch('notification_orders')}
                   onCheckedChange={(v) => form.setValue('notification_orders', v)}
                 />
               </div>
               <Separator />
               <div className="flex items-center justify-between space-x-2">
                 <Label htmlFor="notify-msgs" className="flex flex-col gap-0.5 cursor-pointer">
                   <span className="text-sm font-semibold">Messages</span>
                   <span className="text-xs font-normal text-muted-foreground">Direct messages from customers</span>
                 </Label>
                 <Switch 
                   id="notify-msgs" 
                   checked={form.watch('notification_messages')}
                   onCheckedChange={(v) => form.setValue('notification_messages', v)}
                 />
               </div>
               <Separator />
               <div className="flex items-center justify-between space-x-2">
                 <Label htmlFor="notify-reviews" className="flex flex-col gap-0.5 cursor-pointer">
                   <span className="text-sm font-semibold">Reviews</span>
                   <span className="text-xs font-normal text-muted-foreground">New ratings from buyers</span>
                 </Label>
                 <Switch 
                   id="notify-reviews" 
                   checked={form.watch('notification_reviews')}
                   onCheckedChange={(v) => form.setValue('notification_reviews', v)}
                 />
               </div>
            </CardContent>
          </Card>

          <Card className="bg-primary text-primary-foreground border-0 shadow-lg shadow-primary/20 overflow-hidden relative">
             <div className="absolute top-0 right-0 p-4 opacity-10">
                <Store className="w-24 h-24" />
             </div>
             <CardHeader>
               <CardTitle className="text-lg">Public Store</CardTitle>
               <CardDescription className="text-primary-foreground/80">
                 Preview your storefront appearance
               </CardDescription>
             </CardHeader>
             <CardContent className="space-y-4">
                <p className="text-sm">
                  Make sure your branding is up to date to attract more customers.
                </p>
                <Button 
                   variant="secondary" 
                   className="w-full gap-2"
                   asChild
                >
                  <Link 
                    href={user.seller_profile?.store_slug ? routes.storeView(user.seller_profile.store_slug) : routes.home()} 
                    target="_blank"
                  >
                    View Store
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                </Button>
             </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
