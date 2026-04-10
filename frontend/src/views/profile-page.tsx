'use client';

import { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { motion } from 'framer-motion';
import {
  User,
  Mail,
  Phone,
  Calendar,
  Camera,
  Store,
  Edit3,
  Save,
  X,
  Loader2,
  MapPin,
  Landmark,
  Shield,
  CheckCircle2,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useUIStore, useAuthStore } from '@/store';
import { api } from '@/lib/api-client';
import { formatDate, getInitials } from '@/lib/helpers';
import type { User as DjangoUser } from '@/types/api';

interface ProfileFormValues {
  firstName: string;
  lastName: string;
  phone: string;
  bio: string;
  avatar: string;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export function ProfilePage() {
  const { navigate } = useUIStore();
  const { user, isAuthenticated, setUser } = useAuthStore();
  const [isEditing, setIsEditing] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    setValue,
  } = useForm<ProfileFormValues>();

  // Helper to get display name
  const getDisplayName = (u: DjangoUser) => {
    if (u.first_name || u.last_name) {
      return [u.first_name, u.last_name].filter(Boolean).join(' ');
    }
    return u.username;
  };

  // Load form values when user data is available or when entering edit mode
  useEffect(() => {
    if (user) {
      setValue('firstName', user.first_name || '');
      setValue('lastName', user.last_name || '');
      setValue('phone', user.phone || '');
      setValue('bio', user.profile?.bio || '');
      setValue('avatar', user.avatar || '');
    }
  }, [user, setValue, isEditing]);

  // Auth check
  useEffect(() => {
    if (!isAuthenticated) {
      navigate({ view: 'login' });
    }
  }, [isAuthenticated, navigate]);

  const onSubmit = async (data: ProfileFormValues) => {
    setIsSaving(true);
    try {
      const token = api.getAccessToken();
      const res = await fetch(`${BASE_URL}/accounts/me/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          first_name: data.firstName || undefined,
          last_name: data.lastName || undefined,
          phone: data.phone || undefined,
          avatar: data.avatar || undefined,
          profile: {
            bio: data.bio || undefined,
          },
        }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.message || errData.detail || 'Failed to update profile.');
      }
      // Refetch the full user profile
      const updatedUser = await api.auth.me();
      setUser(updatedUser);
      toast.success('Profile updated successfully.');
      setIsEditing(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update profile.';
      toast.error(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelEdit = () => {
    reset();
    if (user) {
      setValue('firstName', user.first_name || '');
      setValue('lastName', user.last_name || '');
      setValue('phone', user.phone || '');
      setValue('bio', user.profile?.bio || '');
      setValue('avatar', user.avatar || '');
    }
    setIsEditing(false);
  };

  if (!isAuthenticated || !user) return null;

  const displayName = getDisplayName(user);

  return (
    <div className="min-h-[80vh] px-4 py-8">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Profile Header Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card className="border-0 shadow-lg shadow-black/5 overflow-hidden">
            {/* Banner */}
            <div className="h-28 bg-gradient-to-r from-primary/20 via-primary/10 to-orange-100 dark:to-orange-950/30" />
            <CardContent className="pt-0 pb-6 px-6">
              <div className="flex flex-col sm:flex-row sm:items-end gap-4 -mt-12">
                <Avatar className="w-24 h-24 border-4 border-background shadow-lg">
                  <AvatarImage src={user.avatar || undefined} alt={displayName} />
                  <AvatarFallback className="bg-primary/10 text-primary text-xl font-bold">
                    {getInitials(displayName)}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1 sm:pb-1">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
                    <h1 className="text-xl font-bold text-foreground">{displayName}</h1>
                    <div className="flex items-center gap-2">
                      {user.is_verified && (
                        <Badge
                          variant="secondary"
                          className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs"
                        >
                          <CheckCircle2 className="w-3 h-3 mr-1" />
                          Verified
                        </Badge>
                      )}
                      {user.is_seller && (
                        <Badge className="text-xs bg-primary/10 text-primary border-primary/20 hover:bg-primary/15">
                          <Store className="w-3 h-3 mr-1" />
                          Seller
                        </Badge>
                      )}
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground mt-0.5">{user.email}</p>
                </div>
                {!isEditing && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setIsEditing(true)}
                    className="gap-1.5 self-start"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    Edit Profile
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Edit Profile Form / Account Info */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            {isEditing ? (
              <Card className="border-0 shadow-lg shadow-black/5">
                <CardHeader className="pb-4">
                  <CardTitle className="text-lg">Edit Profile</CardTitle>
                  <CardDescription>Update your personal information</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                    {/* Avatar URL */}
                    <div className="space-y-2">
                      <Label htmlFor="avatar" className="text-sm font-medium flex items-center gap-1.5">
                        <Camera className="w-3.5 h-3.5" />
                        Avatar URL
                      </Label>
                      <Input
                        id="avatar"
                        placeholder="https://example.com/avatar.jpg"
                        className="h-10"
                        {...register('avatar')}
                      />
                    </div>

                    {/* First Name */}
                    <div className="space-y-2">
                      <Label htmlFor="firstName" className="text-sm font-medium flex items-center gap-1.5">
                        <User className="w-3.5 h-3.5" />
                        First Name
                      </Label>
                      <Input
                        id="firstName"
                        placeholder="First name"
                        className="h-10"
                        {...register('firstName', {
                          minLength: { value: 2, message: 'Name must be at least 2 characters' },
                        })}
                      />
                      {errors.firstName && (
                        <p className="text-xs text-destructive">{errors.firstName.message}</p>
                      )}
                    </div>

                    {/* Last Name */}
                    <div className="space-y-2">
                      <Label htmlFor="lastName" className="text-sm font-medium flex items-center gap-1.5">
                        <User className="w-3.5 h-3.5" />
                        Last Name
                      </Label>
                      <Input
                        id="lastName"
                        placeholder="Last name"
                        className="h-10"
                        {...register('lastName')}
                      />
                    </div>

                    {/* Phone */}
                    <div className="space-y-2">
                      <Label htmlFor="phone" className="text-sm font-medium flex items-center gap-1.5">
                        <Phone className="w-3.5 h-3.5" />
                        Phone Number
                      </Label>
                      <Input
                        id="phone"
                        placeholder="+255 7XX XXX XXX"
                        className="h-10"
                        {...register('phone')}
                      />
                    </div>

                    {/* Bio */}
                    <div className="space-y-2">
                      <Label htmlFor="bio" className="text-sm font-medium">
                        Bio
                      </Label>
                      <Textarea
                        id="bio"
                        placeholder="Tell us about yourself..."
                        className="min-h-[80px] resize-none"
                        {...register('bio')}
                      />
                    </div>

                    <div className="flex gap-2 pt-2">
                      <Button
                        type="submit"
                        size="sm"
                        disabled={isSaving}
                        className="gap-1.5"
                      >
                        {isSaving ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          <>
                            <Save className="w-3.5 h-3.5" />
                            Save Changes
                          </>
                        )}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleCancelEdit}
                        disabled={isSaving}
                        className="gap-1.5"
                      >
                        <X className="w-3.5 h-3.5" />
                        Cancel
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            ) : (
              <Card className="border-0 shadow-lg shadow-black/5">
                <CardHeader className="pb-4">
                  <CardTitle className="text-lg">Account Information</CardTitle>
                  <CardDescription>Your account details and status</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-muted rounded-lg flex items-center justify-center">
                      <User className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-muted-foreground">Username</p>
                      <p className="text-sm font-medium text-foreground truncate">@{user.username}</p>
                    </div>
                  </div>
                  <Separator />
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-muted rounded-lg flex items-center justify-center">
                      <Mail className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-muted-foreground">Email</p>
                      <p className="text-sm font-medium text-foreground truncate">{user.email}</p>
                    </div>
                  </div>
                  <Separator />
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-muted rounded-lg flex items-center justify-center">
                      <Phone className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-muted-foreground">Phone</p>
                      <p className="text-sm font-medium text-foreground truncate">
                        {user.phone || 'Not set'}
                      </p>
                    </div>
                  </div>
                  <Separator />
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-muted rounded-lg flex items-center justify-center">
                      <Calendar className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-muted-foreground">Member Since</p>
                      <p className="text-sm font-medium text-foreground">
                        {formatDate(user.date_joined)}
                      </p>
                    </div>
                  </div>
                  <Separator />
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-muted rounded-lg flex items-center justify-center">
                      <Shield className="w-4 h-4 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-muted-foreground">Verification</p>
                      <p className="text-sm font-medium text-foreground">
                        {user.is_verified ? 'Verified Account' : 'Unverified'}
                      </p>
                    </div>
                  </div>
                  {user.profile?.bio && (
                    <>
                      <Separator />
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Bio</p>
                        <p className="text-sm text-foreground leading-relaxed">{user.profile.bio}</p>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            )}
          </motion.div>

          {/* Business Info / Become a Seller */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            {user.is_seller ? (
              <Card className="border-0 shadow-lg shadow-black/5">
                <CardHeader className="pb-4">
                  <div className="flex items-center gap-2">
                    <Store className="w-5 h-5 text-primary" />
                    <CardTitle className="text-lg">Business Information</CardTitle>
                  </div>
                  <CardDescription>Your seller profile details</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">
                      <Store className="w-4 h-4 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-muted-foreground">Business Name</p>
                      <p className="text-sm font-medium text-foreground truncate">
                        {user.seller_profile?.business_name || 'Not set'}
                      </p>
                    </div>
                  </div>
                  {user.seller_profile?.business_description && (
                    <>
                      <Separator />
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">
                          <MapPin className="w-4 h-4 text-primary" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-muted-foreground">Description</p>
                          <p className="text-sm font-medium text-foreground truncate">
                            {user.seller_profile.business_description}
                          </p>
                        </div>
                      </div>
                    </>
                  )}
                  <Separator />
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">
                      <Landmark className="w-4 h-4 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-muted-foreground">Payout Method</p>
                      <p className="text-sm font-medium text-foreground truncate">
                        {user.seller_profile?.payout_method || 'Not set'}
                      </p>
                    </div>
                  </div>
                  {user.seller_profile?.verification_status && (
                    <>
                      <Separator />
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">
                          <Shield className="w-4 h-4 text-primary" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-muted-foreground">Verification Status</p>
                          <p className="text-sm font-medium text-foreground capitalize">
                            {user.seller_profile.verification_status}
                          </p>
                        </div>
                      </div>
                    </>
                  )}

                  <Button
                    variant="outline"
                    className="w-full mt-2 gap-2"
                    onClick={() => navigate({ view: 'seller-dashboard' })}
                  >
                    Go to Seller Dashboard
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <Card className="border-0 shadow-lg shadow-black/5 bg-gradient-to-br from-primary/5 to-orange-50 dark:to-orange-950/20 border-dashed border-2 border-primary/20">
                <CardContent className="p-6 flex flex-col items-center text-center gap-4">
                  <div className="w-16 h-16 bg-primary/10 rounded-2xl flex items-center justify-center">
                    <Store className="w-8 h-8 text-primary" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground text-lg">Become a Seller</h3>
                    <p className="text-sm text-muted-foreground mt-1 max-w-xs">
                      Start selling on SmartDalali and reach thousands of buyers across Tanzania.
                    </p>
                  </div>
                  <Button
                    onClick={() => navigate({ view: 'seller-register' })}
                    className="gap-2"
                  >
                    <Store className="w-4 h-4" />
                    Register as Seller
                  </Button>
                </CardContent>
              </Card>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
}
