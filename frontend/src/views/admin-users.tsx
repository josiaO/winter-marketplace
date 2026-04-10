'use client';

import { useRouter } from 'next/navigation';
import { routes } from '@/lib/routes';
import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Users,
  Search,
  Shield,
  ArrowUpRight,
  Loader2,
  UserCog,
  Ban,
  Store,
  MoreHorizontal,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatDate, getInitials, getRelativeTime } from '@/lib/helpers';
import { EmptyState } from '@/components/smartdalali/empty-state';
import type { User, PaginatedResponse } from '@/types/api';

const PAGE_SIZE = 20;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function roleBadgeClass(role: string) {
  switch (role) {
    case 'admin':
      return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
    case 'seller':
      return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400';
    default:
      return 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400';
  }
}

function statusBadgeClass(active: boolean) {
  return active
    ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
    : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AdminUsersPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const [users, setUsers] = useState<User[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  // ── Data fetching ──────────────────────────────────────────────────────
  const fetchUsers = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Record<string, string | number> = { page, limit: PAGE_SIZE };
      if (search) params.search = search;
      if (roleFilter !== 'all') params.role = roleFilter;

      const res: PaginatedResponse<User> = await api.accounts.users(params);
      setUsers(res.results);
      setTotalCount(res.count);
    } catch {
      toast.error('Failed to load users.');
    } finally {
      setIsLoading(false);
    }
  }, [search, roleFilter, page]);

  useEffect(() => {
    if (!isAuthenticated || user?.role !== 'admin') {
      router.push(routes.home());
      return;
    }
    fetchUsers();
  }, [isAuthenticated, user, router, fetchUsers]);

  // ── Actions ────────────────────────────────────────────────────────────
  const handleToggleSellerStatus = async (id: number) => {
    setTogglingId(id);
    try {
      await api.accounts.toggleSellerStatus(id);
      toast.success('Seller status updated successfully.');
      fetchUsers();
    } catch {
      toast.error('Failed to toggle seller status.');
    } finally {
      setTogglingId(null);
    }
  };

  const handleToggleActiveStatus = async (id: number) => {
    setTogglingId(id);
    try {
      await api.accounts.toggleActiveStatus(id);
      toast.success('User active status updated successfully.');
      fetchUsers();
    } catch {
      toast.error('Failed to toggle user status.');
    } finally {
      setTogglingId(null);
    }
  };

  // ── Guard ──────────────────────────────────────────────────────────────
  if (!isAuthenticated || !user || user.role !== 'admin') return null;

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  return (
    <div className="min-h-[80vh] px-4 py-6 sm:py-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* ── Header ─────────────────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-foreground flex items-center gap-2">
              <Users className="w-7 h-7 text-emerald-600" />
              User Management
            </h1>
            <p className="text-muted-foreground mt-1">
              Manage all platform users, sellers, and admins
            </p>
          </div>
          <Button
            variant="outline"
            className="gap-2 shrink-0"
            onClick={() => router.push(routes.adminDashboard())}
          >
            <ArrowUpRight className="w-4 h-4" />
            Dashboard
          </Button>
        </motion.div>

        {/* ── Search + Role Tabs ─────────────────────────────────────────── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <Card className="border-0 shadow-md shadow-black/5">
            <CardContent className="p-4 space-y-4">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  placeholder="Search users by name or email..."
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                  className="pl-9"
                />
              </div>

              {/* Role Tabs */}
              <Tabs value={roleFilter} onValueChange={(val) => { setRoleFilter(val); setPage(1); }}>
                <TabsList>
                  <TabsTrigger value="all">All</TabsTrigger>
                  <TabsTrigger value="user">Buyers</TabsTrigger>
                  <TabsTrigger value="seller">Sellers</TabsTrigger>
                  <TabsTrigger value="admin">Admins</TabsTrigger>
                </TabsList>

                {/* ── Table / Cards ──────────────────────────────────────── */}
                <TabsContent value={roleFilter} className="mt-4">
                  {isLoading ? (
                    <div className="space-y-3">
                      {Array.from({ length: 8 }).map((_, i) => (
                        <Skeleton key={i} className="h-14 w-full" />
                      ))}
                    </div>
                  ) : users.length === 0 ? (
                    <EmptyState
                      icon={Users}
                      title="No users found"
                      description="Try adjusting your search or filter to find who you're looking for."
                    />
                  ) : (
                    <>
                      {/* Desktop Table */}
                      <div className="hidden md:block overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>User</TableHead>
                              <TableHead>Role</TableHead>
                              <TableHead>Seller</TableHead>
                              <TableHead>Status</TableHead>
                              <TableHead>Joined</TableHead>
                              <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {users.map((u) => (
                              <TableRow key={u.id}>
                                <TableCell>
                                  <div className="flex items-center gap-3">
                                    <Avatar className="h-8 w-8">
                                      <AvatarImage src={u.avatar || undefined} />
                                      <AvatarFallback className="text-xs bg-emerald-50 dark:bg-emerald-950/40">
                                        {getInitials(`${u.first_name} ${u.last_name}`)}
                                      </AvatarFallback>
                                    </Avatar>
                                    <div className="min-w-0">
                                      <p className="text-sm font-medium truncate">
                                        {u.first_name ? `${u.first_name} ${u.last_name}`.trim() : u.username}
                                      </p>
                                      <p className="text-xs text-muted-foreground truncate">{u.email}</p>
                                    </div>
                                  </div>
                                </TableCell>
                                <TableCell>
                                  <Badge variant="secondary" className={`text-xs capitalize ${roleBadgeClass(u.role)}`}>
                                    {u.role}
                                  </Badge>
                                </TableCell>
                                <TableCell>
                                  <Badge
                                    variant="secondary"
                                    className={`text-xs ${u.is_seller ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' : 'bg-muted text-muted-foreground'}`}
                                  >
                                    {u.is_seller ? 'Yes' : 'No'}
                                  </Badge>
                                </TableCell>
                                <TableCell>
                                  <Badge variant="secondary" className={`text-xs ${statusBadgeClass(u.is_active)}`}>
                                    {u.is_active ? 'Active' : 'Inactive'}
                                  </Badge>
                                </TableCell>
                                <TableCell className="text-sm text-muted-foreground">
                                  {formatDate(u.date_joined)}
                                </TableCell>
                                <TableCell className="text-right">
                                  <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                      <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                        <MoreHorizontal className="w-4 h-4" />
                                      </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end">
                                      <DropdownMenuItem
                                        onClick={() => handleToggleSellerStatus(u.id)}
                                        disabled={togglingId === u.id || u.role === 'admin'}
                                      >
                                        {togglingId === u.id ? (
                                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                        ) : (
                                          <Store className="w-4 h-4 mr-2" />
                                        )}
                                        {u.is_seller ? 'Remove Seller' : 'Make Seller'}
                                      </DropdownMenuItem>
                                      <DropdownMenuSeparator />
                                      <DropdownMenuItem
                                        onClick={() => handleToggleActiveStatus(u.id)}
                                        disabled={togglingId === u.id || u.role === 'admin'}
                                        className={u.is_active ? 'text-red-600 focus:text-red-600' : ''}
                                      >
                                        {togglingId === u.id ? (
                                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                        ) : u.is_active ? (
                                          <Ban className="w-4 h-4 mr-2" />
                                        ) : (
                                          <UserCog className="w-4 h-4 mr-2" />
                                        )}
                                        {u.is_active ? 'Deactivate User' : 'Activate User'}
                                      </DropdownMenuItem>
                                    </DropdownMenuContent>
                                  </DropdownMenu>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>

                      {/* Mobile Cards */}
                      <div className="md:hidden space-y-3 max-h-[600px] overflow-y-auto">
                        {users.map((u) => (
                          <div key={u.id} className="border rounded-lg p-4 space-y-3">
                            <div className="flex items-center gap-3">
                              <Avatar className="h-10 w-10">
                                <AvatarImage src={u.avatar || undefined} />
                                <AvatarFallback className="text-xs bg-emerald-50 dark:bg-emerald-950/40">
                                  {getInitials(`${u.first_name} ${u.last_name}`)}
                                </AvatarFallback>
                              </Avatar>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">
                                  {u.first_name ? `${u.first_name} ${u.last_name}`.trim() : u.username}
                                </p>
                                <p className="text-xs text-muted-foreground truncate">{u.email}</p>
                              </div>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="sm" className="h-8 w-8 p-0 shrink-0">
                                    <MoreHorizontal className="w-4 h-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem
                                    onClick={() => handleToggleSellerStatus(u.id)}
                                    disabled={togglingId === u.id || u.role === 'admin'}
                                  >
                                    {togglingId === u.id ? (
                                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    ) : (
                                      <Store className="w-4 h-4 mr-2" />
                                    )}
                                    {u.is_seller ? 'Remove Seller' : 'Make Seller'}
                                  </DropdownMenuItem>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem
                                    onClick={() => handleToggleActiveStatus(u.id)}
                                    disabled={togglingId === u.id || u.role === 'admin'}
                                    className={u.is_active ? 'text-red-600 focus:text-red-600' : ''}
                                  >
                                    {togglingId === u.id ? (
                                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    ) : u.is_active ? (
                                      <Ban className="w-4 h-4 mr-2" />
                                    ) : (
                                      <UserCog className="w-4 h-4 mr-2" />
                                    )}
                                    {u.is_active ? 'Deactivate' : 'Activate'}
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <Badge variant="secondary" className={`text-xs capitalize ${roleBadgeClass(u.role)}`}>
                                {u.role}
                              </Badge>
                              <Badge variant="secondary" className={`text-xs ${statusBadgeClass(u.is_active)}`}>
                                {u.is_active ? 'Active' : 'Inactive'}
                              </Badge>
                              <span className="text-xs text-muted-foreground ml-auto">
                                {getRelativeTime(u.date_joined)}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Pagination */}
                      {totalPages > 1 && (
                        <div className="flex items-center justify-between mt-4 pt-4 border-t">
                          <p className="text-sm text-muted-foreground">
                            Page {page} of {totalPages} &middot; {totalCount} users
                          </p>
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={page <= 1}
                              onClick={() => setPage((p) => p - 1)}
                            >
                              <ChevronLeft className="w-4 h-4" />
                              Previous
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={page >= totalPages}
                              onClick={() => setPage((p) => p + 1)}
                            >
                              Next
                              <ChevronRight className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
