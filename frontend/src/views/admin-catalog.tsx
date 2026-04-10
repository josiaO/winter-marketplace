'use client';

import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import {
  Plus,
  Pencil,
  Trash2,
  FolderTree,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAuthStore, useUIStore } from '@/store';
import { api } from '@/lib/api-client';

type FieldType = 'text' | 'long_text' | 'integer' | 'decimal' | 'number' | 'select' | 'boolean' | 'date';

type CategoryRow = {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  icon?: string | null;
  parent?: number | null;
  vertical?: string;
  is_active?: boolean;
  is_service?: boolean;
  is_physical?: boolean;
  order?: number;
  children?: CategoryRow[];
};

type CategoryFieldRow = {
  id: number;
  category: number;
  field_name?: string;
  field_label?: string;
  field_type: FieldType;
  required: boolean;
  choices?: unknown;
  unit?: string | null;
  order?: number;
};

function slugify(s: string): string {
  return s
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-');
}

function flattenTree(cats: CategoryRow[]): Array<{ id: number; name: string; depth: number; parent: number | null }> {
  const out: Array<{ id: number; name: string; depth: number; parent: number | null }> = [];
  const walk = (rows: CategoryRow[], depth: number) => {
    for (const r of rows) {
      out.push({ id: r.id, name: r.name, depth, parent: (r.parent ?? null) as number | null });
      if (Array.isArray(r.children) && r.children.length) walk(r.children, depth + 1);
    }
  };
  walk(cats, 0);
  return out;
}

export function AdminCatalogPage() {
  const navigate = useUIStore((s) => s.navigate);
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const [categories, setCategories] = useState<CategoryRow[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [fields, setFields] = useState<CategoryFieldRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingFields, setIsLoadingFields] = useState(false);

  const flatCats = useMemo(() => flattenTree(categories), [categories]);
  const selected = useMemo(
    () => flatCats.find((c) => c.id === selectedCategoryId) ?? null,
    [flatCats, selectedCategoryId],
  );
  const isSubcategory = Boolean(selected && selected.parent);

  // Dialog state: category
  const [catDialogOpen, setCatDialogOpen] = useState(false);
  const [catMode, setCatMode] = useState<'create' | 'edit'>('create');
  const [catForm, setCatForm] = useState({
    id: 0,
    name: '',
    slug: '',
    parent: '' as string,
    description: '',
    icon: '',
    is_active: true,
    is_service: false,
    is_physical: true,
    order: 0,
  });

  // Dialog state: field
  const [fieldDialogOpen, setFieldDialogOpen] = useState(false);
  const [fieldMode, setFieldMode] = useState<'create' | 'edit'>('create');
  const [fieldForm, setFieldForm] = useState({
    id: 0,
    field_label: '',
    field_name: '',
    field_type: 'text' as FieldType,
    required: false,
    unit: '',
    order: 0,
    choicesText: '', // one per line
  });

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      navigate({ view: 'home' });
      return;
    }
  }, [isAuthenticated, user, navigate]);

  const refreshCategories = async () => {
    setIsLoading(true);
    try {
      const res = await api.catalog.categories({ tree: true, nocache: true });
      const cats = Array.isArray(res) ? res : (res as any).results ?? [];
      setCategories(cats as any);
      if (!selectedCategoryId && cats.length > 0) {
        setSelectedCategoryId((cats[0] as any).id ?? null);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to load categories');
    } finally {
      setIsLoading(false);
    }
  };

  const refreshFields = async (categoryId: number) => {
    setIsLoadingFields(true);
    try {
      const raw = await api.catalog.categoryFieldsByCategory(categoryId);
      setFields((raw as any) as CategoryFieldRow[]);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to load category fields');
      setFields([]);
    } finally {
      setIsLoadingFields(false);
    }
  };

  useEffect(() => {
    void refreshCategories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedCategoryId) {
      setFields([]);
      return;
    }
    void refreshFields(selectedCategoryId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCategoryId]);

  const openCreateCategory = () => {
    setCatMode('create');
    setCatForm({
      id: 0,
      name: '',
      slug: '',
      parent: '',
      description: '',
      icon: '',
      is_active: true,
      is_service: false,
      is_physical: true,
      order: 0,
    });
    setCatDialogOpen(true);
  };

  const openEditCategory = () => {
    if (!selectedCategoryId) return;
    const row = (flatCats.find((c) => c.id === selectedCategoryId) as any) ?? null;
    const full = (categories as any[]).flatMap(() => []); // keep TS happy; actual values are in dialog payload below
    void full;
    setCatMode('edit');
    // Pull from tree by scanning serialized categories (fast enough for admin UI)
    const findNode = (nodes: CategoryRow[]): CategoryRow | null => {
      for (const n of nodes) {
        if (n.id === selectedCategoryId) return n;
        if (n.children?.length) {
          const m = findNode(n.children);
          if (m) return m;
        }
      }
      return null;
    };
    const node = findNode(categories);
    if (!node) return;
    setCatForm({
      id: node.id,
      name: node.name || '',
      slug: node.slug || '',
      parent: node.parent ? String(node.parent) : '',
      description: (node.description as any) || '',
      icon: (node.icon as any) || '',
      is_active: node.is_active !== false,
      is_service: Boolean(node.is_service),
      is_physical: node.is_physical !== false,
      order: Number(node.order || 0),
    });
    setCatDialogOpen(true);
    void row;
  };

  const saveCategory = async () => {
    if (!catForm.name.trim()) {
      toast.error('Category name is required');
      return;
    }
    const slug = (catForm.slug || slugify(catForm.name)).trim();
    if (!slug) {
      toast.error('Category slug is required');
      return;
    }

    try {
      const payload: Record<string, unknown> = {
        name: catForm.name.trim(),
        slug,
        description: catForm.description || '',
        icon: catForm.icon || '',
        is_active: Boolean(catForm.is_active),
        is_service: Boolean(catForm.is_service),
        is_physical: Boolean(catForm.is_physical),
        order: Number(catForm.order || 0),
        ...(catForm.parent ? { parent: Number(catForm.parent) } : { parent: null }),
      };
      if (catMode === 'create') {
        await api.catalog.createCategory(payload as any);
        toast.success('Category created');
      } else {
        await api.catalog.updateCategory(catForm.id, payload);
        toast.success('Category updated');
      }
      setCatDialogOpen(false);
      await refreshCategories();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to save category');
    }
  };

  const deleteCategory = async () => {
    if (!selectedCategoryId) return;
    const ok = window.confirm('Delete this category? This will also delete its subcategories and fields.');
    if (!ok) return;
    try {
      await api.catalog.deleteCategory(selectedCategoryId);
      toast.success('Category deleted');
      setSelectedCategoryId(null);
      await refreshCategories();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to delete category');
    }
  };

  const openCreateField = () => {
    if (!selectedCategoryId) return;
    if (!isSubcategory) {
      toast.error('Fields can only be added to subcategories (categories with a parent).');
      return;
    }
    setFieldMode('create');
    setFieldForm({
      id: 0,
      field_label: '',
      field_name: '',
      field_type: 'text',
      required: false,
      unit: '',
      order: 0,
      choicesText: '',
    });
    setFieldDialogOpen(true);
  };

  const openEditField = (row: CategoryFieldRow) => {
    setFieldMode('edit');
    const choices = Array.isArray((row as any).choices) ? (row as any).choices : null;
    setFieldForm({
      id: row.id,
      field_label: String((row as any).field_label || (row as any).name || ''),
      field_name: String((row as any).field_name || (row as any).key || ''),
      field_type: (String(row.field_type || 'text') as FieldType) || 'text',
      required: Boolean((row as any).required),
      unit: String((row as any).unit || ''),
      order: Number((row as any).order || 0),
      choicesText: choices ? choices.map(String).join('\n') : '',
    });
    setFieldDialogOpen(true);
  };

  const saveField = async () => {
    if (!selectedCategoryId) return;
    if (!isSubcategory) {
      toast.error('Fields can only be added to subcategories.');
      return;
    }
    if (!fieldForm.field_label.trim()) {
      toast.error('Field label is required');
      return;
    }
    const field_name = (fieldForm.field_name || slugify(fieldForm.field_label)).trim();
    if (!field_name) {
      toast.error('Field internal key is required');
      return;
    }

    const choices =
      fieldForm.field_type === 'select'
        ? fieldForm.choicesText
            .split('\n')
            .map((s) => s.trim())
            .filter(Boolean)
        : null;

    const payload: Record<string, unknown> = {
      category: selectedCategoryId,
      field_label: fieldForm.field_label.trim(),
      field_name,
      field_type: fieldForm.field_type,
      required: Boolean(fieldForm.required),
      unit: fieldForm.unit || '',
      order: Number(fieldForm.order || 0),
      choices,
    };

    try {
      if (fieldMode === 'create') {
        await api.catalog.createCategoryField(payload as any);
        toast.success('Field created');
      } else {
        await api.catalog.updateCategoryField(fieldForm.id, payload as any);
        toast.success('Field updated');
      }
      setFieldDialogOpen(false);
      await refreshFields(selectedCategoryId);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to save field');
    }
  };

  const deleteField = async (id: number) => {
    if (!selectedCategoryId) return;
    const ok = window.confirm('Delete this field?');
    if (!ok) return;
    try {
      await api.catalog.deleteCategoryField(id);
      toast.success('Field deleted');
      await refreshFields(selectedCategoryId);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to delete field');
    }
  };

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-foreground">Catalog Management</h1>
              <p className="text-muted-foreground mt-1">
                Manage categories, subcategories, and dynamic listing fields.
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => void refreshCategories()} className="gap-2">
                <RefreshCw className="w-4 h-4" />
                Refresh
              </Button>
              <Button onClick={openCreateCategory} className="gap-2">
                <Plus className="w-4 h-4" />
                New Category
              </Button>
            </div>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Category tree */}
          <Card className="border-0 shadow-md shadow-black/5 lg:col-span-1">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg flex items-center gap-2">
                <FolderTree className="w-4 h-4 text-primary" />
                Categories
              </CardTitle>
              <CardDescription>Select a category to edit and manage fields.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {isLoading ? (
                <p className="text-sm text-muted-foreground">Loading…</p>
              ) : (
                <>
                  <div className="space-y-2">
                    <Label>Select</Label>
                    <Select
                      value={selectedCategoryId ? String(selectedCategoryId) : ''}
                      onValueChange={(v) => setSelectedCategoryId(Number(v))}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Pick a category" />
                      </SelectTrigger>
                      <SelectContent>
                        {flatCats.map((c) => (
                          <SelectItem key={c.id} value={String(c.id)}>
                            {'\u00A0\u00A0'.repeat(c.depth)}
                            {c.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <Separator />

                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" onClick={openEditCategory} disabled={!selectedCategoryId} className="gap-2">
                      <Pencil className="w-4 h-4" />
                      Edit
                    </Button>
                    <Button variant="destructive" onClick={() => void deleteCategory()} disabled={!selectedCategoryId} className="gap-2">
                      <Trash2 className="w-4 h-4" />
                      Delete
                    </Button>
                  </div>

                  {!isSubcategory && selectedCategoryId ? (
                    <p className="text-xs text-muted-foreground">
                      Tip: fields can only be added to <b>subcategories</b> (categories with a parent).
                    </p>
                  ) : null}
                </>
              )}
            </CardContent>
          </Card>

          {/* Right: Fields */}
          <Card className="border-0 shadow-md shadow-black/5 lg:col-span-2">
            <CardHeader className="pb-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <CardTitle className="text-lg">Category Fields</CardTitle>
                  <CardDescription>
                    Dynamic fields shown to sellers when creating a listing under this subcategory.
                  </CardDescription>
                </div>
                <Button onClick={openCreateField} disabled={!selectedCategoryId || !isSubcategory} className="gap-2">
                  <Plus className="w-4 h-4" />
                  New Field
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {(!selectedCategoryId) ? (
                <p className="text-sm text-muted-foreground">Select a category to view fields.</p>
              ) : isLoadingFields ? (
                <p className="text-sm text-muted-foreground">Loading fields…</p>
              ) : fields.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No fields yet. Add some to make seller listing forms dynamic.
                </p>
              ) : (
                <div className="rounded-xl border overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Label</TableHead>
                        <TableHead>Key</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Required</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {fields
                        .slice()
                        .sort((a: any, b: any) => (Number(a.order || 0) - Number(b.order || 0)) || String(a.field_label || '').localeCompare(String(b.field_label || '')))
                        .map((f: any) => (
                          <TableRow key={f.id}>
                            <TableCell className="font-medium">{String(f.field_label || f.name || '')}</TableCell>
                            <TableCell className="font-mono text-xs">{String(f.field_name || f.key || '')}</TableCell>
                            <TableCell className="text-sm">{String(f.field_type || '')}</TableCell>
                            <TableCell>{Boolean(f.required) ? 'Yes' : 'No'}</TableCell>
                            <TableCell className="text-right">
                              <div className="inline-flex gap-2">
                                <Button variant="outline" size="sm" onClick={() => openEditField(f)} className="gap-2">
                                  <Pencil className="w-3.5 h-3.5" />
                                  Edit
                                </Button>
                                <Button variant="destructive" size="sm" onClick={() => void deleteField(f.id)} className="gap-2">
                                  <Trash2 className="w-3.5 h-3.5" />
                                  Delete
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Category dialog */}
      <Dialog open={catDialogOpen} onOpenChange={setCatDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{catMode === 'create' ? 'Create Category' : 'Edit Category'}</DialogTitle>
            <DialogDescription>
              Use parent to create a subcategory. Fields can only be added to subcategories.
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-1 gap-4">
            <div className="space-y-2">
              <Label>Name *</Label>
              <Input
                value={catForm.name}
                onChange={(e) => {
                  const name = e.target.value;
                  setCatForm((p) => ({ ...p, name, slug: p.slug ? p.slug : slugify(name) }));
                }}
                placeholder="e.g. Electronics"
              />
            </div>

            <div className="space-y-2">
              <Label>Slug *</Label>
              <Input
                value={catForm.slug}
                onChange={(e) => setCatForm((p) => ({ ...p, slug: slugify(e.target.value) }))}
                placeholder="electronics"
              />
            </div>

            <div className="space-y-2">
              <Label>Parent (optional)</Label>
              <Select value={catForm.parent} onValueChange={(v) => setCatForm((p) => ({ ...p, parent: v }))}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="No parent (root category)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">No parent (root category)</SelectItem>
                  {flatCats.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {'\u00A0\u00A0'.repeat(c.depth)}
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                value={catForm.description}
                onChange={(e) => setCatForm((p) => ({ ...p, description: e.target.value }))}
                placeholder="Optional description"
              />
            </div>

            <div className="space-y-2">
              <Label>Icon</Label>
              <Input
                value={catForm.icon}
                onChange={(e) => setCatForm((p) => ({ ...p, icon: e.target.value }))}
                placeholder="Optional icon name"
              />
            </div>

            <div className="space-y-2">
              <Label>Order</Label>
              <Input
                type="number"
                value={String(catForm.order)}
                onChange={(e) => setCatForm((p) => ({ ...p, order: Number(e.target.value || 0) }))}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="flex items-start gap-3 rounded-xl border bg-muted/20 p-3">
                <Checkbox
                  checked={catForm.is_active}
                  onCheckedChange={(c) => setCatForm((p) => ({ ...p, is_active: c === true }))}
                  className="mt-0.5"
                />
                <div>
                  <Label className="font-medium">Active</Label>
                  <p className="text-xs text-muted-foreground mt-0.5">Visible to buyers/sellers.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 rounded-xl border bg-muted/20 p-3">
                <Checkbox
                  checked={catForm.is_service}
                  onCheckedChange={(c) => setCatForm((p) => ({ ...p, is_service: c === true }))}
                  className="mt-0.5"
                />
                <div>
                  <Label className="font-medium">Service</Label>
                  <p className="text-xs text-muted-foreground mt-0.5">Category is primarily services.</p>
                </div>
              </div>
              <div className="flex items-start gap-3 rounded-xl border bg-muted/20 p-3 sm:col-span-2">
                <Checkbox
                  checked={catForm.is_physical}
                  onCheckedChange={(c) => setCatForm((p) => ({ ...p, is_physical: c === true }))}
                  className="mt-0.5"
                />
                <div>
                  <Label className="font-medium">Physical</Label>
                  <p className="text-xs text-muted-foreground mt-0.5">Category is primarily physical items.</p>
                </div>
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setCatDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void saveCategory()}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Field dialog */}
      <Dialog open={fieldDialogOpen} onOpenChange={setFieldDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{fieldMode === 'create' ? 'Create Field' : 'Edit Field'}</DialogTitle>
            <DialogDescription>
              Fields are shown to sellers when they pick this subcategory.
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-1 gap-4">
            <div className="space-y-2">
              <Label>Label *</Label>
              <Input
                value={fieldForm.field_label}
                onChange={(e) => {
                  const field_label = e.target.value;
                  setFieldForm((p) => ({
                    ...p,
                    field_label,
                    field_name: p.field_name ? p.field_name : slugify(field_label),
                  }));
                }}
                placeholder="e.g. RAM"
              />
            </div>

            <div className="space-y-2">
              <Label>Internal key *</Label>
              <Input
                value={fieldForm.field_name}
                onChange={(e) => setFieldForm((p) => ({ ...p, field_name: slugify(e.target.value) }))}
                placeholder="e.g. ram"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Type *</Label>
                <Select value={fieldForm.field_type} onValueChange={(v) => setFieldForm((p) => ({ ...p, field_type: v as FieldType }))}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="text">Text</SelectItem>
                    <SelectItem value="long_text">Long text</SelectItem>
                    <SelectItem value="integer">Integer</SelectItem>
                    <SelectItem value="decimal">Decimal</SelectItem>
                    <SelectItem value="select">Select</SelectItem>
                    <SelectItem value="boolean">Boolean</SelectItem>
                    <SelectItem value="date">Date</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Unit</Label>
                <Input
                  value={fieldForm.unit}
                  onChange={(e) => setFieldForm((p) => ({ ...p, unit: e.target.value }))}
                  placeholder="e.g. GB, sqm"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Order</Label>
                <Input
                  type="number"
                  value={String(fieldForm.order)}
                  onChange={(e) => setFieldForm((p) => ({ ...p, order: Number(e.target.value || 0) }))}
                />
              </div>
              <div className="flex items-start gap-3 rounded-xl border bg-muted/20 p-3">
                <Checkbox
                  checked={fieldForm.required}
                  onCheckedChange={(c) => setFieldForm((p) => ({ ...p, required: c === true }))}
                  className="mt-0.5"
                />
                <div>
                  <Label className="font-medium">Required</Label>
                  <p className="text-xs text-muted-foreground mt-0.5">Seller must provide a value.</p>
                </div>
              </div>
            </div>

            {fieldForm.field_type === 'select' ? (
              <div className="space-y-2">
                <Label>Choices (one per line)</Label>
                <Textarea
                  value={fieldForm.choicesText}
                  onChange={(e) => setFieldForm((p) => ({ ...p, choicesText: e.target.value }))}
                  placeholder={'e.g.\nApple\nSamsung\nXiaomi'}
                  rows={4}
                />
                <p className="text-xs text-muted-foreground">
                  For select fields, provide choices; other field types ignore this.
                </p>
              </div>
            ) : null}
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setFieldDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void saveField()}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

