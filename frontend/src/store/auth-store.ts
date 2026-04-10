import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '@/lib/api-client';
import type { User, RegisterPayload, BecomeSellerPayload } from '@/types/api';

// =============================================================================
// State & Actions
// =============================================================================

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  accessToken: string | null;
}

interface AuthActions {
  /** Authenticate with email & password; saves tokens + fetches full profile */
  login: (email: string, password: string) => Promise<void>;
  /** Register a new account; saves tokens + user from response */
  register: (payload: RegisterPayload) => Promise<void>;
  /** Call the Django logout endpoint, then clear local state */
  logout: () => Promise<void>;
  /** Re-fetch the current user profile from /accounts/auth/me/ */
  fetchUser: () => Promise<void>;
  /** Upgrade the current user to seller role */
  becomeSeller: (payload: BecomeSellerPayload) => Promise<void>;
  /** Shallow-merge a partial user object into the store (optimistic UI) */
  updateUser: (partial: Partial<User>) => void;
  /** Replace the full user object in the store (used after login/register) */
  setUser: (user: User) => void;
}

export type AuthStore = AuthState & AuthActions;

// =============================================================================
// Store
// =============================================================================

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      // ── State ──────────────────────────────────────────────────────────────
      user: null,
      isAuthenticated: false,
      isLoading: false,
      accessToken: null,

      // ── Actions ────────────────────────────────────────────────────────────

      login: async (email: string, password: string) => {
        set({ isLoading: true });
        try {
          const res = await api.auth.login({ email, password });
          // Save tokens via ApiClient
          api.setTokens(res.access, res.refresh);
          set({
            user: res.user,
            isAuthenticated: true,
            accessToken: res.access,
          });
          // Fetch full profile (may include seller_profile, groups, etc.)
          try {
            const fullUser = await api.auth.me();
            set({ user: fullUser });
          } catch {
            // Keep the user from login response if me() fails
          }
        } finally {
          set({ isLoading: false });
        }
      },

      register: async (payload: RegisterPayload) => {
        set({ isLoading: true });
        try {
          const res = await api.auth.register(payload);
          if (res.access && res.refresh) {
            api.setTokens(res.access, res.refresh);
          }
          set({
            user: res.user,
            isAuthenticated: true,
            accessToken: res.access || null,
          });
        } finally {
          set({ isLoading: false });
        }
      },

      logout: async () => {
        try {
          await api.auth.logout();
        } catch {
          // Even if the API call fails, clear all local state
        }
        set({
          user: null,
          isAuthenticated: false,
          accessToken: null,
        });
      },

      fetchUser: async () => {
        if (!api.isAuthenticated()) {
          set({ user: null, isAuthenticated: false, accessToken: null });
          return;
        }
        set({ isLoading: true });
        try {
          const user = await api.auth.me();
          set({
            user,
            isAuthenticated: true,
            accessToken: api.getAccessToken(),
          });
        } catch {
          set({ user: null, isAuthenticated: false, accessToken: null });
        } finally {
          set({ isLoading: false });
        }
      },

      becomeSeller: async (_payload: BecomeSellerPayload) => {
        set({ isLoading: true });
        try {
          const res = await api.auth.becomeSeller();
          api.setTokens(res.access, res.refresh);
          const fullUser = (await api.auth.me()) as User;
          set({
            user: fullUser,
            isAuthenticated: true,
            accessToken: res.access,
          });
        } finally {
          set({ isLoading: false });
        }
      },

      updateUser: (partial: Partial<User>) => {
        const current = get().user;
        if (current) {
          set({ user: { ...current, ...partial } });
        }
      },

      setUser: (user: User) => {
        set({ user, isAuthenticated: true });
      },
    }),
    {
      name: 'smartdalali-auth',

      // Only persist a flag — tokens live in localStorage via the ApiClient.
      // The user object is NOT persisted to avoid stale data.
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
      }),

      // After Zustand rehydrates from storage, check if the ApiClient still
      // has valid tokens.  If so, hydrate the user from the backend.
      onRehydrateStorage: () => {
        return (_state, error) => {
          if (error) return;
          if (api.isAuthenticated()) {
            // Use queueMicrotask to avoid blocking the rehydration path
            queueMicrotask(() => {
              useAuthStore.getState().fetchUser();
            });
          }
        };
      },
    }
  )
);
