'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Upload,
  X,
  ImagePlus,
  Loader2,
  ArrowLeft,
  GripVertical,
  ChevronRight,
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
      <img src={row.preview} alt="" className="w-full h-full object-contain" />
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
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState('');
  const [deliveryFree, setDeliveryFree] = useState(true);
  const [deliveryFee, setDeliveryFee] = useState('');
  const [similarRange, setSimilarRange] = useState<{ min: number; max: number } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [catsLoading, setCatsLoading] = useState(true);
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
    const list = Array.from(files).filter((f) => f.type.startsWith('image/') && f.size <= 5 * 1024 * 1024);
    if (!list.length) {
      toast.error('Please use images under 5MB.');
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
        images: files,
      });
      toast.success(asDraft || !isVerified ? 'Draft saved.' : 'Listing published!');
      router.push(routes.sellerListings());
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

      <div className="flex gap-1">
        {[1, 2, 3, ...(isVerified ? [4] : [])].map((s) => (
          <div key={s} className={`h-1 flex-1 rounded-full ${step >= s ? 'bg-primary' : 'bg-muted'}`} />
        ))}
      </div>

      {step === 1 && (
        <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="space-y-4">
          <Card className="border-0 shadow-md">
            <CardHeader>
              <CardTitle>Photos</CardTitle>
              <CardDescription>Up to 8 photos. First photo is the main listing image. Drag to reorder.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-xs text-muted-foreground bg-muted/50 rounded-lg p-3">
                Tip: Good lighting and multiple angles sell faster.
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
                <span className="text-xs">PNG, JPG, WEBP · max 5MB each</span>
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
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
        <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="space-y-4">
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
                <div className="rounded-xl border bg-muted/30 p-3 text-sm space-y-2">
                  {suggestLoading ? (
                    <Skeleton className="h-4 w-2/3" />
                  ) : (
                    <>
                      <p>
                        We think this is:{' '}
                        <span className="font-medium">
                          {suggestParent ? `${suggestParent} › ` : ''}
                          {suggestName}
                        </span>
                        . Is that right?
                      </p>
                      <div className="flex gap-2">
                        <Button size="sm" type="button" onClick={() => toast.success('Category kept')}>
                          Yes
                        </Button>
                        <Button size="sm" variant="outline" type="button" onClick={() => toast.info('Pick a category below')}>
                          Change
                        </Button>
                      </div>
                    </>
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
              <div className="space-y-2">
                <Label>Price (TZS)</Label>
                <Input
                  inputMode="numeric"
                  value={priceStr}
                  onChange={(e) => setPriceStr(e.target.value.replace(/[^\d]/g, ''))}
                  placeholder="0"
                />
                {similarRange && priceNum > 0 && (
                  <p className="text-xs text-muted-foreground">
                    Similar products in this category often list around {formatTZS(similarRange.min)} –{' '}
                    {formatTZS(similarRange.max)}.
                  </p>
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
        <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="space-y-4">
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
            </CardContent>
          </Card>
        </motion.div>
      )}

      {step === 4 && isVerified && (
        <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="space-y-4">
          <Card className="border-0 shadow-md overflow-hidden">
            <CardHeader>
              <CardTitle>Review & publish</CardTitle>
              <CardDescription>Preview how buyers will see your listing.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-2xl border bg-card shadow-sm overflow-hidden max-w-sm mx-auto">
                <div className="aspect-square bg-muted relative">
                  {previewMain ? (
                    <img src={previewMain} alt="" className="w-full h-full object-contain" />
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

      {!isVerified && step === 3 && (
        <Card className="border-amber-200 bg-amber-50/50 dark:bg-amber-950/20">
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
    </div>
  );
}
