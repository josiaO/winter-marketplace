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
      isHydrated: false,

      // ── Actions ────────────────────────────────────────────────────────────

      login: async (email: string, password: string) => {
        set({ isLoading: true });
        try {
          const res = await api.auth.login({ email, password });
          
          // Save tokens via ApiClient (memory-only in browser, cookies set by proxy)
          api.setTokens(res.access, res.refresh);
          
          set({
            user: res.user,
            isAuthenticated: true,
          });

          void get().fetchUser();
        } finally {
          set({ isLoading: false });
        }
      },

      register: async (payload: RegisterPayload) => {
        set({ isLoading: true });
        try {
          const res = await api.auth.register(payload);
          // Backend doesn't return tokens on registration; user must verify or login
          // We don't set user or isAuthenticated here unless tokens were provided
          if ('access' in res && (res as any).access) {
            api.setTokens((res as any).access, (res as any).refresh);
            set({
              user: (res as any).user,
              isAuthenticated: true,
            });
          }
        } finally {
          set({ isLoading: false });
        }
      },

      logout: async () => {
        try {
          await api.auth.logout();
        } catch {
          // even if call fails
        }
        api.setTokens('', ''); // Clear in-memory tokens
        set({
          user: null,
          isAuthenticated: false,
        });
      },

      fetchUser: async () => {
        set({ isLoading: true });
        try {
          const user = await api.auth.me();
          set({
            user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error) {
          // If profile fetch fails, we are definitely not logged in or token is bad
          set({ user: null, isAuthenticated: false, isLoading: false });
          if (api.isUnauthorized(error)) {
            api.setTokens('', '');
          }
        }
      },

      becomeSeller: async (_payload: BecomeSellerPayload) => {
        set({ isLoading: true });
        try {
          const res = await api.auth.becomeSeller();
          api.setTokens(res.access, res.refresh);
          await get().fetchUser();
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
        return (state) => {
          if (!state) return;
          state.setHydrated();
          // Always try to fetch the user on load to verify cookie auth
          void state.fetchUser();
        };
      },
    }
  )
);
