import { api } from '@/lib/api-client';
import type { Cart as DjangoCart } from '@/types/api';
import type { Cart } from '@/types';

export function lineSubtotalFromItem(item: DjangoCart['items'][0]): number {
  if (item.subtotal != null) return Number(item.subtotal);
  return Number(item.listing.price) * item.quantity;
}

/** Map Django cart JSON → local `Cart` shape (header badge + cart UI). */
export function adaptDjangoCart(djangoCart: DjangoCart): Cart {
  return {
    id: String(djangoCart.id),
    userId: String(djangoCart.user),
    items: djangoCart.items.map((item) => ({
      id: String(item.id),
      cartId: String(djangoCart.id),
      listingId: String(item.listing_id),
      listing: {
        id: String(item.listing.id),
        title: item.listing.title,
        price: Number(item.listing.price),
        stockQuantity: item.listing.stock_quantity ?? 99,
        images: (item.listing.images ?? []).map((img) => ({
          id: String(img.id),
          url: img.image,
          altText: null,
          sortOrder: img.order,
          isPrimary: img.is_primary,
        })),
        image: (item.listing as { image?: string }).image,
      },
      quantity: item.quantity,
      lineSubtotal: lineSubtotalFromItem(item),
    })),
  };
}

export async function fetchCartForStore(
  setCart: (cart: Cart | null) => void,
): Promise<void> {
  const djangoCart = await api.commerce.cart();
  setCart(adaptDjangoCart(djangoCart));
}
