import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Cart } from '@/types';

interface CartStore {
  cart: Cart | null;
  itemCount: number;
  setCart: (cart: Cart | null) => void;
  clearCart: () => void;
}

export const useCartStore = create<CartStore>()(
  persist(
    (set) => ({
      cart: null,
      itemCount: 0,

      setCart: (cart) =>
        set({
          cart,
          itemCount: cart?.items?.reduce((sum, item) => sum + item.quantity, 0) ?? 0,
        }),

      clearCart: () =>
        set({
          cart: null,
          itemCount: 0,
        }),
    }),
    {
      name: 'smartdalali-cart',
    }
  )
);
