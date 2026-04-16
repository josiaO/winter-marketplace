import { api } from '@/lib/api-client';
import type { Cart as DjangoCart } from '@/types/api';
import type { Cart } from '@/types';

export function lineSubtotalFromItem(item: DjangoCart['items'][0]): number {
  if (item.subtotal != null) return Number(item.subtotal);
  return Number(item.listing.price) * item.quantity;
}

/** Map Django cart JSON → local `Cart` shape (header badge + cart UI). */
export function adaptDjangoCart(djangoCart: DjangoCart): DjangoCart {
  return {
    ...djangoCart,
    items: djangoCart.items.map((item) => ({
      ...item,
      subtotal: lineSubtotalFromItem(item),
    })),
  };
}

export async function fetchCartForStore(
  setCart: (cart: Cart | null) => void,
): Promise<void> {
  const djangoCart = await api.commerce.cart();
  setCart(adaptDjangoCart(djangoCart));
}
