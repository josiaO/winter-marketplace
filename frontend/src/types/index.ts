// ============ App View (Navigation) ============
// Re-export from store — single source of truth for the discriminated union.
export type { AppView, ViewName } from '@/store/ui-store';

// ============ User ============

export interface User {
  id: string;
  email: string;
  username: string;
  name?: string | null;
  phone?: string | null;
  avatar?: string | null;
  isSeller: boolean;
  isVerified: boolean;
  bio?: string | null;
  businessName?: string | null;
  businessAddress?: string | null;
  bankName?: string | null;
  bankAccount?: string | null;
}

// ============ Category ============

export interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  image?: string | null;
  parentId?: string | null;
  listingCount?: number;
  _count?: { listings?: number };
  createdAt?: string;
  updatedAt?: string;
}

// ============ Listing ============

export interface ListingImage {
  id: string;
  url: string;
  altText?: string | null;
  sortOrder: number;
  isPrimary: boolean;
}

export interface Listing {
  id: string;
  title: string;
  slug: string;
  description: string;
  price: number;
  comparePrice?: number | null;
  condition: string;
  stockQuantity: number;
  status: string;
  categoryId: string;
  category: { id: string; name: string; slug: string };
  seller: {
    id: string;
    username: string;
    name?: string | null;
    avatar?: string | null;
    isVerified: boolean;
  };
  images: ListingImage[];
  _count?: { reviews: number };
  avgRating?: number;
  createdAt?: string;
  updatedAt?: string;
}

// ============ Cart ============

export interface CartItemListing {
  id: string;
  title: string;
  price: number;
  stockQuantity: number;
  images?: ListingImage[];
  image?: string;
}

export interface CartItem {
  id: string;
  cartId: string;
  listingId: string;
  listing: CartItemListing;
  quantity: number;
  /** From Django CartItem.subtotal when present */
  lineSubtotal?: number;
}

export interface Cart {
  id: string;
  userId: string;
  items: CartItem[];
}

// ============ Orders ============

export type OrderStatus =
  | 'pending'
  | 'confirmed'
  | 'processing'
  | 'shipped'
  | 'delivered'
  | 'completed'
  | 'cancelled';

export interface OrderItem {
  id: string;
  orderId: string;
  listingId: string;
  listingTitle: string;
  listingPrice: number;
  listingImage?: string | null;
  quantity: number;
  total: number;
}

export interface Order {
  id: string;
  orderNumber: string;
  status: OrderStatus;
  totalAmount: number;
  subtotalAmount: number;
  shippingFee: number;
  shippingAddress: string;
  shippingPhone: string;
  shippingMethod: string;
  paymentMethod: string;
  buyerId: string;
  sellerId: string;
  items: OrderItem[];
  trackingNumber?: string | null;
  shippedAt?: string | null;
  deliveredAt?: string | null;
  cancelledAt?: string | null;
  cancelReason?: string | null;
  createdAt: string;
  updatedAt: string;
  buyer?: { id: string; username: string; name?: string | null };
  seller?: { id: string; username: string; name?: string | null; isSeller: boolean };
}

// ============ Transaction ============

export type TransactionStatus = 'created' | 'pending' | 'paid' | 'failed' | 'refunded';

export interface Transaction {
  id: string;
  txnNumber: string;
  orderId: string;
  amount: number;
  status: TransactionStatus;
  paymentMethod: string;
  paymentUrl?: string | null;
  providerRef?: string | null;
  paidAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

// ============ Review ============

export interface Review {
  id: string;
  rating: number;
  title?: string | null;
  comment?: string | null;
  listingId: string;
  reviewerId: string;
  reviewer: {
    id: string;
    username: string;
    name?: string | null;
    avatar?: string | null;
  };
  sellerId: string;
  createdAt: string;
  updatedAt: string;
}

// ============ Payout ============

export type PayoutStatus = 'pending' | 'processing' | 'released' | 'failed';

export interface Payout {
  id: string;
  sellerId: string;
  orderId?: string | null;
  amount: number;
  commission: number;
  netAmount: number;
  status: PayoutStatus;
  paymentRef?: string | null;
  releasedAt?: string | null;
  createdAt: string;
  updatedAt: string;
}

// ============ API Responses ============

export interface ListingsResponse {
  listings?: Listing[];
  results?: Listing[];
  data?: Listing[] | { listings?: Listing[] };
  count?: number;
  total?: number;
}

export interface CategoriesResponse {
  categories?: Category[];
  data?: Category[];
}

export interface OrdersResponse {
  orders?: Order[];
  results?: Order[];
  data?: Order[];
  count?: number;
}

export interface DashboardStats {
  totalOrders: number;
  totalRevenue: number;
  totalProducts: number;
  pendingOrders: number;
  avgRating: number;
}
