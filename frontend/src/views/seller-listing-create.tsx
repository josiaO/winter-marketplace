'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  X,
  ImagePlus,
  Loader2,
  ArrowLeft,
  GripVertical,
  ChevronRight,
  Sparkles,
  Info,
} from 'lucide-react';
import { toast } from 'sonner';
import { DndContext, closestCenter, PointerSensor, useSensor, useSensors, DragEndEvent } from '@dnd-kit/core';
import { arrayMove, SortableContext, rectSortingStrategy, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Switch } from '@/components/ui/switch';
import { useAuthStore } from '@/store';
import { canAccessSellerPortal } from '@/lib/auth-roles';
import { api } from '@/lib/api-client';
import { formatTZS } from '@/lib/helpers';
import type { Category } from '@/types/api';
import Link from 'next/link';

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

function DynamicSpecField({
  field,
  value,
  onChange,
}: {
  field: NormalizedCategoryField;
  value: unknown;
  onChange: (val: unknown) => void;
}) {
  const label = (
    <span className="flex items-center gap-1.5 text-sm font-medium">
      {field.field_label}
      {field.unit && <span className="text-xs text-muted-foreground">({field.unit})</span>}
      {field.required && <span className="text-red-500 text-xs">*</span>}
    </span>
  );

  if (field.field_type === 'boolean') {
    return (
      <div className="flex items-center justify-between gap-3 rounded-xl border p-3">
        {label}
        <Switch
          checked={Boolean(value)}
          onCheckedChange={(checked) => onChange(checked)}
        />
      </div>
    );
  }

  if (field.field_type === 'select' && field.choices) {
    return (
      <div className="space-y-1.5">
        {label}
        <select
          className="w-full h-10 rounded-md border bg-background px-3 text-sm"
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
          required={field.required}
        >
          <option value="">Select…</option>
          {field.choices.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      </div>
    );
  }

  if (field.field_type === 'integer' || field.field_type === 'number') {
    return (
      <div className="space-y-1.5">
        {label}
        <Input
          type="number"
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
          required={field.required}
          placeholder={`Enter ${field.field_label.toLowerCase()}`}
        />
      </div>
    );
  }

  if (field.field_type === 'decimal') {
    return (
      <div className="space-y-1.5">
        {label}
        <Input
          type="number"
          step="0.01"
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value === '' ? '' : parseFloat(e.target.value))}
          required={field.required}
          placeholder={`Enter ${field.field_label.toLowerCase()}`}
        />
      </div>
    );
  }

  if (field.field_type === 'long_text') {
    return (
      <div className="space-y-1.5">
        {label}
        <textarea
          className="w-full min-h-[80px] rounded-md border bg-background px-3 py-2 text-sm resize-none"
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
          required={field.required}
          placeholder={`Enter ${field.field_label.toLowerCase()}`}
        />
      </div>
    );
  }

  // default: text / date
  return (
    <div className="space-y-1.5">
      {label}
      <Input
        type={field.field_type === 'date' ? 'date' : 'text'}
        value={String(value ?? '')}
        onChange={(e) => onChange(e.target.value)}
        required={field.required}
        placeholder={`Enter ${field.field_label.toLowerCase()}`}
      />
    </div>
  );
}

type PhotoRow = { id: string; file: File; preview: string };

function flattenCategories(cats: Category[]): Array<{ id: number; name: string; depth: number }> {
  const result: Array<{ id: number; name: string; depth: number }> = [];
  function walk(items: Category[], depth: number) {
    for (const cat of items) {
      result.push({ id: cat.id, name: cat.name, depth });
      if (cat.children && cat.children.length > 0) walk(cat.children, depth + 1);
    }
  }
  walk(cats, 0);
  return result;
}

function SortablePhoto({
  row,
  index,
  onRemove,
}: {
  row: PhotoRow;
  index: number;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: row.id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1 };
  return (
    <div ref={setNodeRef} style={style} className="relative aspect-square rounded-xl overflow-hidden bg-muted group border">
      {row.file.type.startsWith('video/') ? (
        <video src={row.preview} className="w-full h-full object-contain bg-black" controls={false} muted playsInline autoPlay loop />
      ) : (
        <img src={row.preview} alt="" className="w-full h-full object-contain" />
      )}
      {index === 0 && (
        <span className="absolute top-1 left-1 text-[10px] font-semibold bg-primary text-primary-foreground px-1.5 py-0.5 rounded">
          Main
        </span>
      )}
      <button
        type="button"
        className="absolute bottom-1 left-1 p-1.5 rounded-md bg-black/50 text-white touch-none"
        {...attributes}
        {...listeners}
        aria-label="Drag to reorder"
      >
        <GripVertical className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={onRemove}
        className="absolute top-1 right-1 w-7 h-7 rounded-full bg-black/60 text-white flex items-center justify-center"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

export function SellerListingCreatePage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [step, setStep] = useState(1);
  const [flatCategories, setFlatCategories] = useState<Array<{ id: number; name: string; depth: number }>>([]);
  const [photos, setPhotos] = useState<PhotoRow[]>([]);
  const [title, setTitle] = useState('');
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const [suggestParent, setSuggestParent] = useState<string | null>(null);
  const [suggestName, setSuggestName] = useState<string | null>(null);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [priceStr, setPriceStr] = useState('');
  const [condition, setCondition] = useState<'new' | 'used' | 'refurbished'>('new');
  const [trackStock, setTrackStock] = useState(false);
  const [stockQty, setStockQty] = useState(1);
  const [lowStock, setLowStock] = useState(3);
  const [allowBackorders, setAllowBackorders] = useState(false);
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState('');
  const [deliveryFree, setDeliveryFree] = useState(true);
  const [deliveryFee, setDeliveryFee] = useState('');
  const [similarRange, setSimilarRange] = useState<{ min: number; max: number } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [catsLoading, setCatsLoading] = useState(true);
  const [categoryFields, setCategoryFields] = useState<NormalizedCategoryField[]>([]);
  const [specs, setSpecs] = useState<Record<string, unknown>>({});
  const [fieldsLoading, setFieldsLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const suggestTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const isVerified = user?.seller_profile?.verification_status === 'verified';

  const priceNum = useMemo(() => {
    const n = parseFloat(priceStr.replace(/,/g, ''));
    return Number.isFinite(n) ? n : 0;
  }, [priceStr]);

  useEffect(() => {
    if (!isAuthenticated) {
      router.push(routes.login());
      return;
    }
    if (!canAccessSellerPortal(user)) {
      toast.error('You must be a seller to create listings.');
      router.push(routes.sellerRegister());
    }
  }, [isAuthenticated, user, router]);

  useEffect(() => {
    const city = user?.profile?.city || '';
    const addr = user?.profile?.address || '';
    setLocation([city, addr].filter(Boolean).join(', '));
  }, [user]);

  useEffect(() => {
    void (async () => {
      try {
        const result = await api.catalog.categories({ tree: true });
        const cats = Array.isArray(result) ? result : (result as { results?: Category[] }).results ?? [];
        setFlatCategories(flattenCategories(cats as Category[]));
      } catch {
        toast.error('Failed to load categories.');
      } finally {
        setCatsLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (suggestTimer.current) clearTimeout(suggestTimer.current);
    const t = title.trim();
    if (t.length < 3) {
      setSuggestParent(null);
      setSuggestName(null);
      return;
    }
    suggestTimer.current = setTimeout(async () => {
      setSuggestLoading(true);
      try {
        const res = await api.catalog.suggestFromTitle({ title: t });
        if (res.category_id) {
          setSuggestParent(res.parent_name);
          setSuggestName(res.category_name);
          setCategoryId(res.category_id);
        } else {
          setSuggestParent(null);
          setSuggestName(null);
        }
      } catch {
        setSuggestParent(null);
        setSuggestName(null);
      } finally {
        setSuggestLoading(false);
      }
    }, 500);
    return () => {
      if (suggestTimer.current) clearTimeout(suggestTimer.current);
    };
  }, [title]);

  // Fetch dynamic category fields when categoryId changes
  useEffect(() => {
    if (!categoryId) {
      setCategoryFields([]);
      setSpecs({});
      return;
    }
    setFieldsLoading(true);
    void api.catalog.categoryFields(categoryId)
      .then((raw) => {
        const normalized = normalizeCategoryFields(raw as any);
        setCategoryFields(normalized);
        // Preserve any existing spec values for fields that still exist
        setSpecs((prev) => {
          const next: Record<string, unknown> = {};
          for (const f of normalized) {
            if (prev[f.field_name] !== undefined) next[f.field_name] = prev[f.field_name];
          }
          return next;
        });
      })
      .catch(() => setCategoryFields([]))
      .finally(() => setFieldsLoading(false));
  }, [categoryId]);

  useEffect(() => {
    if (!categoryId || priceNum <= 0) {
      setSimilarRange(null);
      return;
    }
    const h = setTimeout(async () => {
      try {
        const r = await api.marketplace.items({ category: categoryId, page_size: 40 });
        const rows = (r as { results?: { price: number; id: number }[] }).results ?? [];
        const prices = rows.filter((l) => l.id && l.price > 0).map((l) => l.price);
        if (prices.length < 2) {
          setSimilarRange(null);
          return;
        }
        setSimilarRange({ min: Math.min(...prices), max: Math.max(...prices) });
      } catch {
        setSimilarRange(null);
      }
    }, 400);
    return () => clearTimeout(h);
  }, [categoryId, priceStr]);

  const processFiles = useCallback(async (files: FileList | File[]) => {
    const newRows: PhotoRow[] = [];
    const list = Array.from(files).filter((f) => {
      if (f.type.startsWith('image/')) return f.size <= 5 * 1024 * 1024;
      if (f.type.startsWith('video/')) return f.size <= 50 * 1024 * 1024 && (f.type === 'video/mp4' || f.type === 'video/webm');
      return false;
    });
    if (!list.length) {
      toast.error('Please use images under 5MB or videos (MP4/WEBM) under 50MB.');
      return;
    }
    for (const file of list) {
      const preview = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(new Error('read'));
        reader.onload = () => resolve(String(reader.result || ''));
        reader.readAsDataURL(file);
      }).catch(() => '');
      if (!preview) continue;
      newRows.push({ id: crypto.randomUUID(), file, preview });
    }
    setPhotos((p) => {
      const merged = [...p, ...newRows].slice(0, 8);
      if (p.length + newRows.length > 8) toast.message('Only the first 8 photos are kept.');
      return merged;
    });
  }, []);

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    setPhotos((items) => {
      const oldIndex = items.findIndex((i) => i.id === active.id);
      const newIndex = items.findIndex((i) => i.id === over.id);
      if (oldIndex < 0 || newIndex < 0) return items;
      return arrayMove(items, oldIndex, newIndex);
    });
  };

  const publish = async (asDraft: boolean) => {
    if (photos.length === 0) {
      toast.error('Add at least one photo.');
      return;
    }
    if (!title.trim() || title.trim().length < 3) {
      toast.error('Enter a product name.');
      return;
    }
    if (!categoryId) {
      toast.error('Pick a category.');
      return;
    }
    if (priceNum < 1) {
      toast.error('Enter a valid price.');
      return;
    }
    if (!deliveryFree) {
      const fee = parseFloat(deliveryFee);
      if (!Number.isFinite(fee) || fee <= 0) {
        toast.error('Enter a delivery fee or choose free delivery.');
        return;
      }
    }
    if (!asDraft && !isVerified) {
      toast.message('Saved as draft', { description: 'Verify your identity to publish live.' });
    }

    setSubmitting(true);
    try {
      const files = photos.map((p) => p.file);
      const desc = description.trim() || ' ';
      await api.listings.create({
        title: title.trim(),
        description: desc,
        price: priceNum,
        condition,
        category: categoryId,
        address: location.trim() || undefined,
        city: user?.profile?.city || undefined,
        listing_type: 'sale',
        status: asDraft || !isVerified ? 'draft' : 'published',
        is_published: !asDraft && isVerified,
        delivery_is_free: deliveryFree,
        ...(!deliveryFree ? { delivery_fee: parseFloat(deliveryFee) } : {}),
        track_inventory: trackStock,
        stock_quantity: trackStock ? stockQty : undefined,
        low_stock_threshold: trackStock ? lowStock : undefined,
        allow_backorders: allowBackorders,
        ...(Object.keys(specs).length > 0 ? { specs } : {}),
        images: files,
      });
      toast.success(asDraft || !isVerified ? '✅ Listing saved as draft! Complete Step 3 to go live.' : '🎉 Listing published!');
      // Redirect to dashboard so onboarding progress refreshes and Step 3 unlocks immediately
      router.push(routes.sellerDashboard());
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to save listing.';
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const previewMain = photos[0]?.preview;

  return (
    <div className="min-h-[80vh] px-3 sm:px-4 py-6 max-w-lg mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={() => router.push(routes.sellerListings())}>
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div>
          <h1 className="text-xl font-bold">Add product</h1>
          <p className="text-xs text-muted-foreground">Step {step} of {isVerified ? 4 : 3}</p>
        </div>
      </div>

      <div className="flex gap-1.5 h-1.5 px-1">
        {[1, 2, 3, ...(isVerified ? [4] : [])].map((s) => (
          <div key={s} className="flex-1 relative">
            <div className={`absolute inset-0 rounded-full transition-all duration-500 ${step >= s ? 'bg-primary shadow-[0_0_8px_rgba(var(--primary),0.4)]' : 'bg-muted'}`} />
            {step === s && (
              <motion.div
                layoutId="step-indicator"
                className="absolute inset-0 bg-primary rounded-full"
                transition={{ type: 'spring', bounce: 0.2, duration: 0.6 }}
              />
            )}
          </div>
        ))}
      </div>

      <AnimatePresence mode="wait">

      {step === 1 && (
        <motion.div key="step-1" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="space-y-4">
          <Card className="border-0 shadow-md">
            <CardHeader>
              <CardTitle>Photos</CardTitle>
              <CardDescription>Up to 8 photos. First photo is the main listing image. Drag to reorder.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-xs text-muted-foreground bg-muted/50 rounded-lg p-3">
                Tip: Good lighting and multiple angles sell faster. You can also include up to 1 video (MP4/WebM).
              </p>
              <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                <SortableContext items={photos.map((p) => p.id)} strategy={rectSortingStrategy}>
                  {photos.length > 0 && (
                    <div className="grid grid-cols-2 gap-2">
                      {photos.map((p, i) => (
                        <SortablePhoto key={p.id} row={p} index={i} onRemove={() => setPhotos((x) => x.filter((y) => y.id !== p.id))} />
                      ))}
                    </div>
                  )}
                </SortableContext>
              </DndContext>
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                className="w-full border-2 border-dashed rounded-2xl p-10 flex flex-col items-center gap-2 text-muted-foreground hover:border-primary/50 hover:bg-muted/30"
              >
                <ImagePlus className="w-10 h-10" />
                <span className="text-sm font-medium text-foreground">Tap to add photos</span>
                <span className="text-xs">PNG, JPG, WEBP (max 5MB) · MP4, WEBM (max 50MB)</span>
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/*,video/mp4,video/webm"
                multiple
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) {
                    void processFiles(e.target.files);
                  }
                  e.target.value = '';
                }}
              />
              <Button className="w-full h-12" disabled={photos.length === 0} onClick={() => setStep(2)}>
                Continue
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {step === 2 && (
        <motion.div key="step-2" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="space-y-4">
          <Card className="border-0 shadow-md">
            <CardHeader>
              <CardTitle>The basics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Product name</Label>
                <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Samsung Galaxy A54" />
              </div>
              {(suggestLoading || suggestName) && (
                <div className="rounded-2xl border-0 bg-primary/5 dark:bg-primary/10 p-4 relative overflow-hidden ring-1 ring-primary/20">
                  <div className="absolute top-0 right-0 p-2 opacity-20">
                    <Sparkles className="w-8 h-8 text-primary" />
                  </div>
                  {suggestLoading ? (
                    <div className="flex items-center gap-3">
                      <Loader2 className="w-4 h-4 animate-spin text-primary" />
                      <Skeleton className="h-4 w-2/3" />
                    </div>
                  ) : (
                    <div className="space-y-3 relative z-10">
                      <div className="flex items-center gap-2 text-primary">
                        <Sparkles className="w-4 h-4" />
                        <span className="text-xs font-bold uppercase tracking-wider">Auto-Categorized</span>
                      </div>
                      <p className="text-sm font-semibold leading-relaxed">
                        Is <span className="text-primary font-bold underline decoration-2 decoration-primary/30 underline-offset-4 tracking-tight">
                          {suggestParent ? `${suggestParent} › ` : ''}{suggestName}
                        </span> correct?
                      </p>
                      <div className="flex gap-2">
                        <Button size="sm" type="button" className="rounded-lg h-8 px-4 font-bold shadow-md shadow-primary/20" onClick={() => toast.success('Category kept')}>
                          Yes, perfect
                        </Button>
                        <Button size="sm" variant="outline" type="button" className="rounded-lg h-8 px-4 font-bold bg-white/50" onClick={() => toast.info('Pick a category below')}>
                          No, change
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}
              <div className="space-y-2">
                <Label>Category</Label>
                {catsLoading ? (
                  <Skeleton className="h-10 w-full" />
                ) : (
                  <select
                    className="w-full h-10 rounded-md border bg-background px-3 text-sm"
                    value={categoryId ?? ''}
                    onChange={(e) => setCategoryId(Number(e.target.value) || null)}
                  >
                    <option value="">Select…</option>
                    {flatCategories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {'\u00A0'.repeat(c.depth * 2)}
                        {c.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* ── Dynamic Category Fields ──────────────────────────────── */}
              {fieldsLoading && (
                <div className="space-y-3">
                  <Skeleton className="h-4 w-36" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              )}
              {!fieldsLoading && categoryFields.length > 0 && (
                <div className="space-y-3 rounded-xl border border-primary/20 bg-primary/5 dark:bg-primary/10 p-4">
                  <p className="text-xs font-bold uppercase tracking-wider text-primary">Category Details</p>
                  {categoryFields.map((field) => (
                    <DynamicSpecField
                      key={field.id}
                      field={field}
                      value={specs[field.field_name]}
                      onChange={(val) =>
                        setSpecs((prev) => ({ ...prev, [field.field_name]: val }))
                      }
                    />
                  ))}
                </div>
              )}

              <div className="space-y-2">
                <Label>Price (TZS)</Label>
                <Input
                  inputMode="numeric"
                  value={priceStr}
                  onChange={(e) => setPriceStr(e.target.value.replace(/[^\d]/g, ''))}
                  placeholder="0"
                />
                {similarRange && priceNum > 0 && (
                  <div className="rounded-xl bg-emerald-50 dark:bg-emerald-500/10 p-3 border border-emerald-100 dark:border-emerald-500/20">
                    <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-400 mb-2">
                      <Info className="w-3.5 h-3.5" />
                      <span className="text-[11px] font-bold uppercase tracking-wider">Price Benchmark</span>
                    </div>
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-[11px] font-medium opacity-70">
                        <span>Min: {formatTZS(similarRange.min)}</span>
                        <span>Max: {formatTZS(similarRange.max)}</span>
                      </div>
                      <div className="h-1.5 w-full bg-emerald-200/30 dark:bg-emerald-500/5 rounded-full relative overflow-hidden">
                         <div 
                           className="absolute h-full bg-emerald-500 rounded-full transition-all duration-500"
                           style={{ 
                             left: `${Math.max(0, Math.min(100, (similarRange.min / similarRange.max) * 100))}%`,
                             right: `${100 - Math.max(0, Math.min(100, (100)))}%`
                           }}
                         />
                         {/* Marker for current price */}
                         <div 
                           className="absolute top-0 bottom-0 w-1 bg-primary z-20 shadow-[0_0_4px_rgba(var(--primary),0.5)]"
                           style={{ left: `${Math.max(0, Math.min(100, (priceNum / similarRange.max) * 100))}%` }}
                         />
                      </div>
                      <p className="text-[11px] text-emerald-800/80 dark:text-emerald-300/80 font-medium">
                        SmartDalali hint: Similar items sell for {formatTZS(similarRange.min)} - {formatTZS(similarRange.max)}.
                      </p>
                    </div>
                  </div>
                )}
              </div>
              <div className="space-y-2">
                <Label>Condition</Label>
                <div className="grid grid-cols-3 gap-2">
                  {(['new', 'used', 'refurbished'] as const).map((c) => (
                    <Button
                      key={c}
                      type="button"
                      size="lg"
                      variant={condition === c ? 'default' : 'outline'}
                      className="h-12 capitalize"
                      onClick={() => setCondition(c)}
                    >
                      {c}
                    </Button>
                  ))}
                </div>
              </div>
              <div className="rounded-xl border p-3 space-y-2">
                <div className="flex items-start gap-3">
                  <Checkbox
                    id="df"
                    checked={deliveryFree}
                    onCheckedChange={(v) => {
                      setDeliveryFree(v === true);
                    }}
                  />
                  <Label htmlFor="df" className="text-sm leading-snug">
                    Free delivery for buyers
                  </Label>
                </div>
                {!deliveryFree && (
                  <Input
                    placeholder="Delivery fee (TZS)"
                    value={deliveryFee}
                    onChange={(e) => setDeliveryFee(e.target.value.replace(/[^\d]/g, ''))}
                  />
                )}
              </div>
              <div className="flex gap-2">
                <Button type="button" variant="outline" className="flex-1" onClick={() => setStep(1)}>
                  Back
                </Button>
                <Button
                  className="flex-1"
                  disabled={!title.trim() || !categoryId || priceNum < 1}
                  onClick={() => setStep(3)}
                >
                  Continue
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {step === 3 && (
        <motion.div key="step-3" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="space-y-4">
          <Card className="border-0 shadow-md">
            <CardHeader>
              <CardTitle>Stock & details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium">Track stock?</p>
                  <p className="text-xs text-muted-foreground">Turn off for one-of-a-kind items.</p>
                </div>
                <Switch checked={trackStock} onCheckedChange={(c) => setTrackStock(c === true)} />
              </div>
              {trackStock && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label>Quantity</Label>
                    <Input
                      type="number"
                      min={1}
                      value={stockQty}
                      onChange={(e) => setStockQty(Math.max(1, parseInt(e.target.value, 10) || 1))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Alert me when stock reaches</Label>
                    <Input
                      type="number"
                      min={0}
                      value={lowStock}
                      onChange={(e) => setLowStock(Math.max(0, parseInt(e.target.value, 10) || 0))}
                    />
                  </div>
                </div>
              )}
              {trackStock && (
                <div className="flex items-start gap-3 pt-1">
                  <Checkbox
                    id="backorders"
                    checked={allowBackorders}
                    onCheckedChange={(c) => setAllowBackorders(c === true)}
                  />
                  <div>
                    <Label htmlFor="backorders" className="text-sm font-medium">
                      Allow backorders
                    </Label>
                    <p className="text-[11px] text-muted-foreground">
                      Customers can purchase even if out of stock.
                    </p>
                  </div>
                </div>
              )}
              <div className="space-y-2">
                <Label>Description (optional)</Label>
                <Textarea rows={4} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} />
                <p className="text-xs text-muted-foreground text-right">{description.length}/2000</p>
              </div>
              <div className="space-y-2">
                <Label>Location</Label>
                <Input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="City, area…" />
              </div>
              <div className="flex gap-2">
                <Button type="button" variant="outline" className="flex-1" onClick={() => setStep(2)}>
                  Back
                </Button>
                <Button className="flex-1" onClick={() => (isVerified ? setStep(4) : void publish(true))}>
                  {isVerified ? 'Continue' : 'Save draft'}
                </Button>
              </div>

              {!isVerified && (
                <Card className="border-amber-200 bg-amber-50/50 dark:bg-amber-950/20 mt-4">
                  <CardContent className="pt-6 text-sm space-y-3">
                    <p className="font-medium text-foreground">Your listing will be saved as a draft until you are verified.</p>
                    <p className="text-muted-foreground">
                      Complete identity verification to publish live listings and earn the verified badge.
                    </p>
                    <Button asChild>
                      <Link href={routes.sellerVerification()}>Go to verification</Link>
                    </Button>
                  </CardContent>
                </Card>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}

      {step === 4 && isVerified && (
        <motion.div key="step-4" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="space-y-4">
          <Card className="border-0 shadow-md overflow-hidden">
            <CardHeader>
              <CardTitle>Review & publish</CardTitle>
              <CardDescription>Preview how buyers will see your listing.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl border bg-card shadow-sm overflow-hidden max-w-sm mx-auto">
                <div className="aspect-square bg-muted relative">
                  {previewMain ? (
                    photos[0]?.file.type.startsWith('video/') ? (
                      <video src={previewMain} className="w-full h-full object-contain bg-black" muted playsInline />
                    ) : (
                      <img src={previewMain} alt="" className="w-full h-full object-contain" />
                    )
                  ) : (
                    <Upload className="w-10 h-10 m-auto text-muted-foreground absolute inset-0 m-auto" />
                  )}
                </div>
                <div className="p-4 space-y-1">
                  <p className="font-semibold line-clamp-2">{title || 'Product name'}</p>
                  <p className="text-lg font-bold text-primary">{formatTZS(priceNum || 0)}</p>
                  <p className="text-xs text-muted-foreground capitalize">{condition}</p>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <Button className="h-12" disabled={submitting} onClick={() => void publish(false)}>
                  {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Publish now'}
                </Button>
                <Button variant="outline" className="h-12" disabled={submitting} onClick={() => void publish(true)}>
                  Save as draft
                </Button>
                <Button type="button" variant="ghost" onClick={() => setStep(3)}>
                  Back
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      </AnimatePresence>
    </div>
  );
}
