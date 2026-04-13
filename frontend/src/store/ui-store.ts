import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIStore {
  /** Global search query (synced with header input) */
  searchQuery: string;
  /** Currently selected category slug / id for filtering */
  selectedCategory: string | null;

  /** Buyer browse layout */
  browseLayout: 'grid' | 'list';
  /** Compact cards for small screens */
  browseDensity: 'compact' | 'default';

  /** Update the global search query */
  setSearchQuery: (query: string) => void;
  /** Set / clear the selected category filter */
  setSelectedCategory: (category: string | null) => void;
  setBrowseLayout: (layout: 'grid' | 'list') => void;
  setBrowseDensity: (density: 'compact' | 'default') => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      searchQuery: '',
      selectedCategory: null,
      browseLayout: 'grid',
      browseDensity: 'compact',

      setSearchQuery: (searchQuery) => set({ searchQuery }),

      setSelectedCategory: (selectedCategory) => set({ selectedCategory }),
      setBrowseLayout: (browseLayout) => set({ browseLayout }),
      setBrowseDensity: (browseDensity) => set({ browseDensity }),
    }),
    {
      name: 'smartdalali-ui',
      partialize: (state) => ({
        searchQuery: state.searchQuery,
        selectedCategory: state.selectedCategory,
        browseLayout: state.browseLayout,
        browseDensity: state.browseDensity,
      }),
    }
  )
);
