import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIStore {
  /** Global search query (synced with header input) */
  searchQuery: string;
  /** Currently selected category slug / id for filtering */
  selectedCategory: string | null;

  /** Update the global search query */
  setSearchQuery: (query: string) => void;
  /** Set / clear the selected category filter */
  setSelectedCategory: (category: string | null) => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      searchQuery: '',
      selectedCategory: null,

      setSearchQuery: (searchQuery) => set({ searchQuery }),

      setSelectedCategory: (selectedCategory) => set({ selectedCategory }),
    }),
    {
      name: 'smartdalali-ui',
      partialize: (state) => ({
        searchQuery: state.searchQuery,
        selectedCategory: state.selectedCategory,
      }),
    }
  )
);
