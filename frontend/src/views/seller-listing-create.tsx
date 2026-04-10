'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { motion } from 'framer-motion';
import {
  Upload,
  X,
  ImagePlus,
  Loader2,
  ArrowLeft,
  Eye,
  Save,
  Send,
} from 'lucide-react';
import { toast } from 'sonner';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useUIStore, useAuthStore } from '@/store';
import { canAccessSellerPortal } from '@/lib/auth-roles';
import { api } from '@/lib/api-client';
import type { Category } from '@/types/api';

// ─── Schema ────────────────────────────────────────────────────────────────────

const listingSchema = z
  .object({
    title: z.string().min(3, 'Title must be at least 3 characters').max(200, 'Title too long'),
    description: z.string().min(20, 'Description must be at least 20 characters').max(5000, 'Description too long'),
    price: z.coerce.number().min(1, 'Price must be at least 1'),
    condition: z.enum(['new', 'used', 'refurbished'] as const, { required_error: 'Select a condition' }),
    category: z.coerce.number().min(1, 'Select a category'),
    city: z.string().optional().default(''),
    address: z.string().optional().default(''),
    listing_type: z.enum(['sale', 'rent', 'service'] as const, { required_error: 'Select a type' }),
    delivery_is_free: z.boolean(),
    delivery_fee: z.coerce.number().min(0).optional(),
  })
  .superRefine((data, ctx) => {
    if (!data.delivery_is_free) {
      const fee = data.delivery_fee;
      if (fee === undefined || fee === null || Number(fee) <= 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'Enter a delivery fee (TZS) or enable free delivery',
          path: ['delivery_fee'],
        });
      }
    }
  });

type ListingFormData = z.infer<typeof listingSchema>;

type FieldType = 'text' | 'long_text' | 'integer' | 'decimal' | 'number' | 'select' | 'boolean' | 'date';

interface NormalizedCategoryField {
  id: number;
  field_name: string;
  field_label: string;
  field_type: FieldType;
  required: boolean;
  choices: string[] | null;
  unit?: string | null;
  order: number;
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-');
}

function normalizeCategoryFields(raw: any[]): NormalizedCategoryField[] {
  const rows: NormalizedCategoryField[] = [];
  for (const f of raw || []) {
    const field_name = String(f.field_name || f.key || '').trim();
    if (!field_name) continue;
    const field_label = String(f.field_label || f.name || field_name);
    const field_type = (String(f.field_type || 'text') as FieldType) || 'text';
    const choicesRaw = f.choices ?? f.options ?? null;
    const choices = Array.isArray(choicesRaw) ? choicesRaw.map((c) => String(c)) : null;
    rows.push({
      id: Number(f.id),
      field_name,
      field_label,
      field_type,
      required: Boolean(f.required),
      choices,
      unit: typeof f.unit === 'string' ? f.unit : null,
      order: Number(f.order || 0),
    });
  }
  rows.sort((a, b) => (a.order ?? 0) - (b.order ?? 0) || a.field_label.localeCompare(b.field_label));
  return rows;
}

// ─── Helper: flatten category tree ────────────────────────────────────────────

function flattenCategories(cats: Category[]): Array<{ id: number; name: string; depth: number }> {
  const result: Array<{ id: number; name: string; depth: number }> = [];
  function walk(items: Category[], depth: number) {
    for (const cat of items) {
      result.push({ id: cat.id, name: cat.name, depth });
      if (cat.children && cat.children.length > 0) {
        walk(cat.children, depth + 1);
      }
    }
  }
  walk(cats, 0);
  return result;
}

// ─── Component ─────────────────────────────────────────────────────────────────

export function SellerListingCreatePage() {
  const { navigate } = useUIStore();
  const { user, isAuthenticated } = useAuthStore();
  const [categories, setCategories] = useState<Category[]>([]);
  const [flatCategories, setFlatCategories] = useState<Array<{ id: number; name: string; depth: number }>>([]);
  const [images, setImages] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDraft, setIsDraft] = useState(false);
  const [isLoadingCategories, setIsLoadingCategories] = useState(true);
  const [categoryFields, setCategoryFields] = useState<NormalizedCategoryField[]>([]);
  const [specs, setSpecs] = useState<Record<string, unknown>>({});
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const form = useForm<ListingFormData>({
    resolver: zodResolver(listingSchema),
    defaultValues: {
      title: '',
      description: '',
      price: 0,
      condition: 'new',
      category: 0,
      city: '',
      address: '',
      listing_type: 'sale',
      delivery_is_free: true,
      delivery_fee: 0,
    },
  });

  // ─── Auth guard ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) {
      navigate({ view: 'login' });
      return;
    }
    if (!canAccessSellerPortal(user)) {
      toast.error('You must be a seller to create listings.');
      navigate({ view: 'seller-register' });
    }
  }, [isAuthenticated, user, navigate]);

  // ─── Load categories ──────────────────────────────────────────────────────
  useEffect(() => {
    async function loadCategories() {
      try {
        const result = await api.catalog.categories({ tree: true });
        const cats = Array.isArray(result) ? result : (result as any).results ?? [];
        setCategories(cats as Category[]);
        setFlatCategories(flattenCategories(cats as Category[]));
      } catch {
        toast.error('Failed to load categories.');
      } finally {
        setIsLoadingCategories(false);
      }
    }
    loadCategories();
  }, []);

  // ─── Load dynamic fields for selected subcategory ─────────────────────────
  const selectedCategoryId = form.watch('category');
  useEffect(() => {
    async function loadFields() {
      if (!selectedCategoryId) {
        setCategoryFields([]);
        setSpecs({});
        return;
      }
      try {
        const raw = await api.catalog.categoryFields(selectedCategoryId);
        const normalized = normalizeCategoryFields(raw as any);
        setCategoryFields(normalized);
        setSpecs({});
      } catch {
        setCategoryFields([]);
        setSpecs({});
      }
    }
    void loadFields();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCategoryId]);

  // ─── Image handling ───────────────────────────────────────────────────────
  const processFiles = useCallback((files: FileList | File[]) => {
    const validFiles = Array.from(files).filter(
      (f) => f.type.startsWith('image/') && f.size <= 5 * 1024 * 1024
    );
    if (validFiles.length === 0) {
      toast.error('Please upload image files under 5MB.');
      return;
    }
    setImages((prev) => [...prev, ...validFiles].slice(0, 8));
    validFiles.forEach((file) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        setPreviews((prev) => [...prev, e.target?.result as string].slice(0, 8));
      };
      reader.readAsDataURL(file);
    });
  }, []);

  const removeImage = useCallback((index: number) => {
    setImages((prev) => prev.filter((_, i) => i !== index));
    setPreviews((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      processFiles(e.dataTransfer.files);
    },
    [processFiles]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  // ─── Submit ────────────────────────────────────────────────────────────────
  const onSubmit = async (data: ListingFormData) => {
    setIsSubmitting(true);
    try {
      // Validate required dynamic specs
      const missing: string[] = [];
      for (const f of categoryFields) {
        if (!f.required) continue;
        const v = specs[f.field_name];
        const empty =
          v === undefined ||
          v === null ||
          (typeof v === 'string' && v.trim() === '');
        if (empty) missing.push(f.field_label);
      }
      if (missing.length > 0) {
        toast.error(`Please fill required fields: ${missing.slice(0, 3).join(', ')}${missing.length > 3 ? '…' : ''}`);
        setIsSubmitting(false);
        return;
      }

      const specsPayload: Record<string, unknown> = {};
      for (const f of categoryFields) {
        const raw = specs[f.field_name];
        if (raw === undefined || raw === null || raw === '') continue;
        if (f.field_type === 'integer') {
          const n = Number(raw);
          if (!Number.isNaN(n)) specsPayload[f.field_name] = Math.trunc(n);
          continue;
        }
        if (f.field_type === 'decimal' || f.field_type === 'number') {
          const n = Number(raw);
          if (!Number.isNaN(n)) specsPayload[f.field_name] = n;
          continue;
        }
        if (f.field_type === 'boolean') {
          specsPayload[f.field_name] = Boolean(raw);
          continue;
        }
        specsPayload[f.field_name] = raw;
      }

      await api.listings.create({
        title: data.title,
        description: data.description,
        price: data.price,
        condition: data.condition,
        category: data.category,
        city: data.city || undefined,
        address: data.address || undefined,
        listing_type: data.listing_type,
        status: isDraft ? 'draft' : 'active',
        is_published: !isDraft,
        delivery_is_free: data.delivery_is_free,
        ...(!data.delivery_is_free ? { delivery_fee: data.delivery_fee } : {}),
        ...(Object.keys(specsPayload).length > 0 ? { specs: specsPayload } : {}),
        ...(images.length > 0 ? { images } : {}),
      });
      toast.success(isDraft ? 'Draft saved successfully!' : 'Listing published successfully!');
      navigate({ view: 'seller-listings' });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create listing.';
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isAuthenticated || !user) return null;

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate({ view: 'seller-listings' })}
              className="shrink-0"
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-foreground">
                Create New Listing
              </h1>
              <p className="text-muted-foreground mt-1">
                Add a new product or service to your store
              </p>
            </div>
          </div>
        </motion.div>

        {/* Form */}
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          {/* Basic Info */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
          >
            <Card className="border-0 shadow-md shadow-black/5">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg">Basic Information</CardTitle>
                <CardDescription>
                  Provide the essential details about your listing
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Title */}
                <div className="space-y-2">
                  <Label htmlFor="title">Title *</Label>
                  <Input
                    id="title"
                    placeholder="e.g. iPhone 15 Pro Max 256GB"
                    {...form.register('title')}
                    className={form.formState.errors.title ? 'border-destructive' : ''}
                  />
                  {form.formState.errors.title && (
                    <p className="text-xs text-destructive">{form.formState.errors.title.message}</p>
                  )}
                </div>

                {/* Description */}
                <div className="space-y-2">
                  <Label htmlFor="description">Description *</Label>
                  <Textarea
                    id="description"
                    placeholder="Describe your product or service in detail. Include specifications, condition, and any other relevant information..."
                    rows={5}
                    {...form.register('description')}
                    className={form.formState.errors.description ? 'border-destructive' : ''}
                  />
                  {form.formState.errors.description && (
                    <p className="text-xs text-destructive">{form.formState.errors.description.message}</p>
                  )}
                </div>

                {/* Price & Type Row */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="price">Price (TZS) *</Label>
                    <Input
                      id="price"
                      type="number"
                      placeholder="0"
                      min={1}
                      {...form.register('price', { valueAsNumber: true })}
                      className={form.formState.errors.price ? 'border-destructive' : ''}
                    />
                    {form.formState.errors.price && (
                      <p className="text-xs text-destructive">{form.formState.errors.price.message}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label>Type *</Label>
                    <Select
                      value={form.watch('listing_type')}
                      onValueChange={(val) => form.setValue('listing_type', val as any)}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="sale">For Sale</SelectItem>
                        <SelectItem value="rent">For Rent</SelectItem>
                        <SelectItem value="service">Service</SelectItem>
                      </SelectContent>
                    </Select>
                    {form.formState.errors.listing_type && (
                      <p className="text-xs text-destructive">{form.formState.errors.listing_type.message}</p>
                    )}
                  </div>
                </div>

                {/* Delivery: stored on listing; checkout prefers seller fees over platform grid when sum > 0 */}
                <div className="space-y-3 rounded-xl border bg-muted/20 p-4">
                  <div className="flex items-start gap-3">
                    <Checkbox
                      id="delivery-free"
                      checked={form.watch('delivery_is_free')}
                      onCheckedChange={(c) => {
                        const free = c === true;
                        form.setValue('delivery_is_free', free);
                        if (free) form.setValue('delivery_fee', 0);
                      }}
                      className="mt-0.5"
                    />
                    <div>
                      <Label htmlFor="delivery-free" className="cursor-pointer font-medium">
                        Free delivery for buyers
                      </Label>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        If unchecked, set your delivery charge (TZS). It is multiplied by quantity
                        at checkout for this item.
                      </p>
                    </div>
                  </div>
                  {!form.watch('delivery_is_free') && (
                    <div className="space-y-2 pl-7">
                      <Label htmlFor="delivery_fee">Delivery fee (TZS) *</Label>
                      <Input
                        id="delivery_fee"
                        type="number"
                        min={1}
                        placeholder="e.g. 5000"
                        {...form.register('delivery_fee', { valueAsNumber: true })}
                        className={
                          form.formState.errors.delivery_fee ? 'border-destructive' : ''
                        }
                      />
                      {form.formState.errors.delivery_fee && (
                        <p className="text-xs text-destructive">
                          {form.formState.errors.delivery_fee.message}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                {/* Condition */}
                <div className="space-y-2">
                  <Label>Condition *</Label>
                  <div className="flex flex-wrap gap-2">
                    {(['new', 'used', 'refurbished'] as const).map((cond) => (
                      <Button
                        key={cond}
                        type="button"
                        variant={form.watch('condition') === cond ? 'default' : 'outline'}
                        size="sm"
                        className="capitalize"
                        onClick={() => form.setValue('condition', cond)}
                      >
                        {cond}
                      </Button>
                    ))}
                  </div>
                  {form.formState.errors.condition && (
                    <p className="text-xs text-destructive">{form.formState.errors.condition.message}</p>
                  )}
                </div>

                {/* Category */}
                <div className="space-y-2">
                  <Label>Category *</Label>
                  {isLoadingCategories ? (
                    <Skeleton className="h-10 w-full" />
                  ) : (
                    <Select
                      value={form.watch('category') ? String(form.watch('category')) : undefined}
                      onValueChange={(val) => form.setValue('category', Number(val))}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a category" />
                      </SelectTrigger>
                      <SelectContent>
                        {flatCategories.map((cat) => (
                          <SelectItem key={cat.id} value={String(cat.id)}>
                            {'\u00A0\u00A0'.repeat(cat.depth)}{cat.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                  {form.formState.errors.category && (
                    <p className="text-xs text-destructive">{form.formState.errors.category.message}</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Category-specific fields */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
          >
            <Card className="border-0 shadow-md shadow-black/5">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg">Category Details</CardTitle>
                <CardDescription>
                  These fields change based on the selected subcategory.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {selectedCategoryId ? (
                  categoryFields.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No extra fields for this category yet.
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {categoryFields.map((f) => {
                        const key = f.field_name;
                        const label = f.unit ? `${f.field_label} (${f.unit})` : f.field_label;
                        const required = f.required;
                        const value = specs[key];
                        const set = (v: unknown) => setSpecs((prev) => ({ ...prev, [key]: v }));

                        if (f.field_type === 'long_text') {
                          return (
                            <div key={key} className="space-y-2 sm:col-span-2">
                              <Label>
                                {label} {required ? <span className="text-destructive">*</span> : null}
                              </Label>
                              <Textarea
                                value={typeof value === 'string' ? value : ''}
                                onChange={(e) => set(e.target.value)}
                                placeholder={label}
                                rows={4}
                              />
                            </div>
                          );
                        }

                        if (f.field_type === 'select') {
                          return (
                            <div key={key} className="space-y-2">
                              <Label>
                                {label} {required ? <span className="text-destructive">*</span> : null}
                              </Label>
                              <Select
                                value={typeof value === 'string' ? value : ''}
                                onValueChange={(val) => set(val)}
                              >
                                <SelectTrigger className="w-full">
                                  <SelectValue placeholder={`Select ${f.field_label}`} />
                                </SelectTrigger>
                                <SelectContent>
                                  {(f.choices || []).map((c) => (
                                    <SelectItem key={slugify(c)} value={c}>
                                      {c}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>
                          );
                        }

                        if (f.field_type === 'boolean') {
                          return (
                            <div key={key} className="space-y-2">
                              <div className="flex items-start gap-3 rounded-xl border bg-muted/20 p-3">
                                <Checkbox
                                  checked={Boolean(value)}
                                  onCheckedChange={(c) => set(c === true)}
                                  className="mt-0.5"
                                />
                                <div>
                                  <Label className="font-medium">
                                    {label} {required ? <span className="text-destructive">*</span> : null}
                                  </Label>
                                  <p className="text-xs text-muted-foreground mt-0.5">
                                    Toggle {f.field_label.toLowerCase()}.
                                  </p>
                                </div>
                              </div>
                            </div>
                          );
                        }

                        if (f.field_type === 'date') {
                          return (
                            <div key={key} className="space-y-2">
                              <Label>
                                {label} {required ? <span className="text-destructive">*</span> : null}
                              </Label>
                              <Input
                                type="date"
                                value={typeof value === 'string' ? value : ''}
                                onChange={(e) => set(e.target.value)}
                              />
                            </div>
                          );
                        }

                        const isNumber = f.field_type === 'integer' || f.field_type === 'decimal' || f.field_type === 'number';
                        return (
                          <div key={key} className="space-y-2">
                            <Label>
                              {label} {required ? <span className="text-destructive">*</span> : null}
                            </Label>
                            <Input
                              type={isNumber ? 'number' : 'text'}
                              value={value === undefined || value === null ? '' : String(value)}
                              onChange={(e) => set(e.target.value)}
                              placeholder={f.field_label}
                            />
                          </div>
                        );
                      })}
                    </div>
                  )
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Select a category to see dynamic fields.
                  </p>
                )}
              </CardContent>
            </Card>
          </motion.div>

          {/* Location */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Card className="border-0 shadow-md shadow-black/5">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg">Location</CardTitle>
                <CardDescription>
                  Where is this item available or where can the service be provided?
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="city">City</Label>
                    <Input
                      id="city"
                      placeholder="e.g. Dar es Salaam"
                      {...form.register('city')}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="address">Specific Location</Label>
                    <Input
                      id="address"
                      placeholder="e.g. Kariakoo, Ilala"
                      {...form.register('address')}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Images */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
          >
            <Card className="border-0 shadow-md shadow-black/5">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg">Images</CardTitle>
                <CardDescription>
                  Add up to 8 images. The first image will be the primary photo. Max 5MB each.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Preview Grid */}
                {previews.length > 0 && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {previews.map((preview, index) => (
                      <div key={preview} className="relative group aspect-square rounded-lg overflow-hidden bg-muted">
                        <img
                          src={preview}
                          alt={`Upload preview ${index + 1}`}
                          className="w-full h-full object-cover"
                        />
                        {index === 0 && (
                          <div className="absolute top-1 left-1">
                            <span className="text-[10px] font-semibold bg-primary text-primary-foreground px-1.5 py-0.5 rounded">
                              Primary
                            </span>
                          </div>
                        )}
                        <button
                          type="button"
                          onClick={() => removeImage(index)}
                          className="absolute top-1 right-1 w-6 h-6 bg-black/60 hover:bg-black/80 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                        >
                          <X className="w-3 h-3 text-white" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Drop Zone */}
                <div
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onClick={() => fileInputRef.current?.click()}
                  className={`
                    border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
                    ${isDragging
                      ? 'border-primary bg-primary/5'
                      : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50'
                    }
                  `}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files) processFiles(e.target.files);
                      e.target.value = '';
                    }}
                  />
                  <ImagePlus className="w-10 h-10 mx-auto mb-3 text-muted-foreground/50" />
                  <p className="text-sm font-medium text-foreground">
                    Drop images here or click to upload
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    PNG, JPG, WEBP up to 5MB each · Max 8 images
                  </p>
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Submit Actions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="flex flex-col sm:flex-row gap-3 justify-end"
          >
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate({ view: 'seller-listings' })}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="outline"
              disabled={isSubmitting}
              onClick={() => { setIsDraft(true); setTimeout(() => form.handleSubmit(onSubmit)(), 0); }}
              className="gap-2"
            >
              {isSubmitting && isDraft ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Save as Draft
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting}
              onClick={() => setIsDraft(false)}
              className="gap-2"
            >
              {isSubmitting && !isDraft ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              Publish Listing
            </Button>
          </motion.div>
        </form>
      </div>
    </div>
  );
}
