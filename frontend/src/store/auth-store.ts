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
  isHydrated: boolean;
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
  /** Set hydrated state */
  setHydrated: () => void;
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
      isHydrated: false,

      // ── Actions ────────────────────────────────────────────────────────────

      login: async (email: string, password: string) => {
        set({ isLoading: true });
        try {
          const res = await api.auth.login({ email, password });
          // Save tokens via ApiClient
          api.setTokens(res.access, res.refresh);
          
          // Set initial user info from login response ASAP
          set({
            user: res.user,
            isAuthenticated: true,
            accessToken: res.access,
          });

          // Fetch full profile in background but don't block the login flow
          // unless necessary. Actually, we'll fetch it now but only await it 
          // if we want to be 100% sure. For better UX, we'll update the store
          // whenever it arrives.
          void get().fetchUser();
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
        // If we don't even have a token, we aren't authenticated locally.
        if (!api.isAuthenticated()) {
          set({ user: null, isAuthenticated: false, accessToken: null, isLoading: false });
          return;
        }

        set({ isLoading: true });
        try {
          const user = await api.auth.me();
          set({
            user,
            isAuthenticated: true,
            accessToken: api.getAccessToken(),
            isLoading: false,
          });
        } catch (error) {
          console.error('Profile sync failed:', error);
          // If profile fetch fails with 401, it means tokens are invalid.
          if (api.isUnauthorized(error)) {
            await get().logout();
          }
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

      setHydrated: () => set({ isHydrated: true }),
    }),
    {
      name: 'smartdalali-auth',

      // Only persist a flag — tokens live in localStorage via the ApiClient.
      // The user object is NOT persisted to avoid stale data.
      partialize: (state) => ({
        isAuthenticated: state.isAuthenticated,
        user: state.user, // Persist user to show immediate UI on reload
      }),

      // After Zustand rehydrates from storage, check if the ApiClient still
      // has valid tokens.  If so, hydrate the user from the backend.
      onRehydrateStorage: () => {
        return (state, error) => {
          if (error || !state) {
            setTimeout(() => useAuthStore.setState({ isHydrated: true }), 0);
            return;
          }

          // If we are authenticated, refresh the user in the background
          if (api.isAuthenticated()) {
            state.setHydrated();
            
            // Background fetch to ensure data is fresh
            queueMicrotask(() => {
              void state.fetchUser();
            });
          } else {
            state.setHydrated();
          }
        };
      },
    }
  )
);
