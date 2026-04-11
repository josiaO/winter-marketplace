// =============================================================================
// SmartDalali Django REST API Types
// Comprehensive TypeScript types matching the backend API at /api/v1/
// =============================================================================

// ============ Pagination ============

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ============ Auth Types ============

export interface TokenResponse {
  access: string;
  refresh: string;
}

export interface TokenResponseWithUser extends TokenResponse {
  user: User;
}

export type UserRole = 'admin' | 'seller' | 'user';

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  is_seller: boolean;
  /** Django staff; required to match admin API access when not superuser. */
  is_staff?: boolean;
  is_superuser?: boolean;
  is_active: boolean;
  is_verified: boolean;
  phone: string | null;
  avatar: string | null;
  profile: UserProfile;
  seller_profile: SellerProfile | null;
  groups: string[];
  date_joined: string;
}

export interface UserProfile {
  id: number;
  user: number;
  bio: string | null;
  avatar: string | null;
  phone: string | null;
  city: string | null;
  address: string | null;
  date_of_birth: string | null;
}

export type VerificationStatus = 'pending' | 'verified' | 'rejected' | 'unverified';

export interface SellerProfile {
  id: number;
  user: number;
  business_name: string;
  business_description: string | null;
  tin_number: string | null;
  license_number: string | null;
  id_document: string | null;
  license_document: string | null;
  verification_status: VerificationStatus;
  is_verified: boolean;
  payout_method: string | null;
  payout_details: Record<string, unknown> | null;
  store: Store | null;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  confirm_password?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
}

export interface PasswordResetPayload {
  email: string;
}

export interface PasswordResetConfirmPayload {
  uid: string;
  token: string;
  new_password: string;
  confirm_password: string;
}

export interface ChangePasswordPayload {
  old_password: string;
  new_password: string;
  confirm_password: string;
}

export interface BecomeSellerPayload {
  business_name: string;
  business_description?: string;
  tin_number?: string;
  license_number?: string;
  payout_method?: string;
  payout_details?: Record<string, unknown>;
}

export interface OtpPayload {
  email: string;
}

export interface OtpVerifyPayload {
  email: string;
  code: string;
}

// ============ Listing / Catalog Types ============

export type ListingCondition = 'new' | 'used' | 'refurbished';
export type ListingStatus = 'published' | 'draft' | 'archived';
export type ListingType = 'product' | 'service';
export type Currency = 'TZS' | 'USD' | 'KES' | 'UGX';

export interface ListingImage {
  id: number;
  image: string;
  is_primary: boolean;
  order: number;
}

export interface ListingSeller {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  avatar: string | null;
  is_seller: boolean;
  is_verified: boolean;
  seller_profile?: {
    id: number;
    business_name: string;
    store?: {
      id: number;
      name: string;
      slug: string;
    } | null;
  } | null;
}

export interface ListingCategory {
  id: number;
  name: string;
  slug: string;
  icon: string | null;
  image: string | null;
  parent: number | null;
}

export interface ListingAttributeValueRow {
  id: number;
  attribute_id: number;
  key: string;
  label: string;
  name: string;
  value: string | number | boolean | null;
}

export interface Listing {
  id: number;
  title: string;
  slug: string;
  description: string;
  price: number;
  currency: Currency;
  condition: ListingCondition;
  category: ListingCategory;
  city: string | null;
  location: string | null;
  is_verified: boolean;
  is_featured: boolean;
  view_count: number;
  /** Available on listing detail / cart payloads from Django. */
  stock_quantity?: number;
  status: ListingStatus;
  listing_type: ListingType;
  seller?: ListingSeller;
  owner?: ListingSeller;
  images: ListingImage[];
  /** Legacy / optional; prefer specs + attribute_values */
  attributes?: Record<string, unknown>;
  specs?: Record<string, unknown> | null;
  attribute_values?: ListingAttributeValueRow[];
  delivery_is_free?: boolean;
  delivery_fee?: string | number | null;
  created_at: string;
  updated_at: string;
}

export interface CreateListingPayload {
  title: string;
  description: string;
  price: number;
  currency?: Currency;
  condition: ListingCondition;
  category: number;
  city?: string;
  location?: string;
  listing_type?: ListingType;
  images?: File[];
  attributes?: Record<string, unknown>;
  specs?: Record<string, unknown>;
  delivery_is_free?: boolean;
  delivery_fee?: number | null;
}

export interface UpdateListingPayload extends Partial<CreateListingPayload> {
  id: number;
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  icon: string | null;
  image: string | null;
  parent: number | null;
  children?: Category[];
  field_count: number;
  listing_count: number;
}

export interface CategoryField {
  id: number;
  name: string;
  label: string;
  field_type: string;
  choices: Array<{ value: string; label: string }> | null;
  required: boolean;
  placeholder: string | null;
  help_text: string | null;
  order: number;
}

export interface CategoryAttribute {
  id: number;
  category: number;
  name: string;
  label: string;
  field_type: string;
  choices: string[] | null;
  required: boolean;
  default_value: string | null;
  help_text: string | null;
  order: number;
}

export interface Store {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  logo: string | null;
  cover: string | null;
  seller: number;
  is_verified: boolean;
  is_followed: boolean;
  followers_count: number;
  listings_count: number;
  created_at: string;
}

// ============ Commerce Types ============

export interface CartItem {
  id: number;
  listing: Listing;
  listing_id: number;
  quantity: number;
  /** Line total from backend (price_at_time × quantity). Prefer over client math. */
  subtotal?: string | number;
  price_at_time?: string | number;
  total?: number;
}

export interface Cart {
  id: number;
  user: number;
  items: CartItem[];
  total: number;
  item_count: number;
}

export type OrderStatus =
  | 'pending'
  | 'confirmed'
  | 'processing'
  | 'shipped'
  | 'arrived'
  | 'delivered'
  | 'completed'
  | 'cancelled'
  | 'refunded'
  | 'disputed';

export type ShippingMethod = 'standard' | 'express' | 'pickup';
export type PaymentMethod = 'mobile_money' | 'bank_transfer' | 'card' | 'cash_on_delivery';
export type PaymentChannel = 'tigo_pesa' | 'm_pesa' | 'airtel_money' | 'halopesa' | 'azam_pay' | 'bank';

/** Matches Django `OrderItemSerializer`; legacy flat fields optional. */
export interface OrderItem {
  id: number;
  order?: number;
  listing?: Listing | null;
  listing_id?: number;
  quantity: number;
  price_at_time?: string | number;
  subtotal?: string | number;
  created_at?: string;
  updated_at?: string;
  listing_title?: string;
  listing_price?: number;
  listing_image?: string | null;
  total?: number;
}

export interface OrderBuyer {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  avatar: string | null;
  phone: string | null;
}

export interface OrderSeller {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  avatar: string | null;
  phone: string | null;
  is_verified: boolean;
  seller_profile?: {
    id: number;
    business_name: string;
  } | null;
}

export interface Order {
  id: number;
  order_number?: string;
  /** Django OrderSerializer camelCase alias */
  orderNumber?: string;
  status: OrderStatus;
  buyer: OrderBuyer;
  seller: OrderSeller;
  items: OrderItem[];
  subtotal?: number | string;
  shipping_cost?: number | string;
  total?: number;
  total_amount?: string | number;
  totalAmount?: string | number;
  shipping_address: string;
  shipping_phone: string;
  shipping_method: ShippingMethod;
  payment_method: PaymentMethod;
  payment_channel: PaymentChannel | null;
  tracking_number: string | null;
  dispute: Dispute | null;
  /** Django `OrderSerializer.get_escrow` — engine transaction snapshot (status is uppercase, e.g. HOLD). */
  escrow?: {
    id?: string;
    reference?: string;
    status?: string;
    payment_method?: string;
    amount?: string;
    currency?: string;
  } | null;
  transaction: Transaction | null;
  escrow_transaction: Transaction | null;
  payment_url: string | null;
  transaction_reference: string | null;
  created_at: string;
  updated_at: string;
}

/** GET /commerce/cart/shipping_options/ */
export interface ShippingOptionRow {
  method: string;
  label: string;
  description: string;
  fee: string;
  currency: string;
}

export interface CheckoutPayload {
  shipping_address: string;
  shipping_phone: string;
  shipping_method: ShippingMethod;
  payment_method: PaymentMethod;
  payment_channel?: PaymentChannel;
}

/** POST /commerce/orders/confirm-payment-return/ */
export interface ConfirmPaymentReturnPayload {
  transaction_reference: string;
}

export interface EscrowTransactionSummary {
  reference?: string;
  linked_order_id?: number | null;
  status?: string;
}

export interface ConfirmPaymentReturnResponse {
  success: boolean;
  transaction: EscrowTransactionSummary & Record<string, unknown>;
}

export interface WishlistItem {
  id: number;
  listing: Listing;
  listing_id: number;
  created_at: string;
}

export type TransactionStatus =
  | 'created'
  | 'pending'
  | 'paid'
  | 'completed'
  | 'failed'
  | 'refunded'
  | 'released';

export interface Transaction {
  id: number;
  order: number;
  status: TransactionStatus;
  amount: number;
  fee: number;
  net_amount: number;
  payment_method: PaymentMethod;
  provider_ref: string | null;
  payment_url: string | null;
  created_at: string;
}

export interface Payout {
  id: number;
  seller: number;
  amount: number;
  fee: number;
  net_amount: number;
  status: 'pending' | 'processing' | 'released' | 'failed';
  payment_ref: string | null;
  payout_method: string | null;
  payout_details: Record<string, unknown> | null;
  created_at: string;
  released_at: string | null;
}

// ============ Trust / Review Types ============

export interface Review {
  id: number;
  listing: number | Listing;
  reviewer: {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
    avatar: string | null;
  };
  rating: number;
  comment: string;
  seller_reply: string | null;
  created_at: string;
}

export interface CreateReviewPayload {
  listing: number;
  rating: number;
  comment: string;
}

export type ReportReason =
  | 'spam'
  | 'inappropriate'
  | 'fraud'
  | 'duplicate'
  | 'wrong_category'
  | 'misleading'
  | 'other';

export type ReportStatus = 'pending' | 'reviewed' | 'resolved' | 'dismissed';

export interface Report {
  id: number;
  reporter: number | { id: number; username: string };
  listing: number | Listing;
  reason: ReportReason;
  description: string;
  status: ReportStatus;
  admin_notes: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface CreateReportPayload {
  listing?: number | null;
  reported_user?: number | null;
  report_type?: 'listing' | 'user' | 'review' | 'message';
  reason: ReportReason;
  description: string;
}

export type DocumentStatus = 'not_submitted' | 'pending' | 'approved' | 'rejected';

export interface Verification {
  id: number;
  user: number;
  national_id_number: string | null;
  national_id_front: string | null;
  national_id_back: string | null;
  tin_number: string | null;
  tin_certificate: string | null;
  business_license_number: string | null;
  business_license_document: string | null;
  id_status: DocumentStatus;
  tin_status: DocumentStatus;
  business_license_status: DocumentStatus;
  is_identity_verified: boolean;
  verification_date: string | null;
  reviewer_notes: string | null;
  created_at: string;
  updated_at: string;
}

// ============ Communication Types ============

export interface ConversationParticipant {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  avatar: string | null;
}

export interface Conversation {
  id: number;
  participants: ConversationParticipant[];
  last_message: {
    id: number;
    text: string;
    created_at: string;
    sender: number;
    is_read?: boolean;
  } | null;
  unread_count: number;
  listing?: Listing | null;
  order?: Order | null;
  created_at: string;
}

export interface Message {
  id: number;
  conversation: number;
  sender: number;
  text: string;
  attachment: string | null;
  read_at: string | null;
  status?: string;
  is_deleted?: boolean;
  created_at: string;
}

export type NotificationType =
  | 'order'
  | 'payment'
  | 'message'
  | 'listing'
  | 'review'
  | 'verification'
  | 'system'
  | 'dispute'
  | 'payout'
  | 'promotion';

export interface Notification {
  id: number;
  user: number;
  title: string;
  body: string;
  type: NotificationType;
  data: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
}

export interface SupportRequest {
  id: number;
  user: number;
  subject: string;
  message: string;
  status: 'open' | 'in_progress' | 'resolved' | 'closed';
  priority: 'low' | 'medium' | 'high';
  attachments: string[];
  created_at: string;
  updated_at: string;
}

export interface DeviceToken {
  id: number;
  user: number;
  token: string;
  device_type: 'ios' | 'android' | 'web';
  created_at: string;
}

// ============ Dispute Types ============

export type DisputeStatus = 'open' | 'under_review' | 'resolved' | 'dismissed';

export type DisputeReason =
  | 'item_not_received'
  | 'item_not_as_described'
  | 'damaged_item'
  | 'wrong_item'
  | 'quality_issue'
  | 'seller_unresponsive'
  | 'payment_issue'
  | 'other';

export interface Dispute {
  id: number;
  order: number | Order;
  initiated_by: number | { id: number; username: string };
  reason: DisputeReason;
  evidence_video: string | null;
  evidence_images: string[];
  status: DisputeStatus;
  resolution: string | null;
  admin_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateDisputePayload {
  order: number;
  reason: DisputeReason;
  description?: string;
  evidence_video?: File;
  evidence_images?: File[];
}

export interface ResolveDisputePayload {
  resolution: string;
  admin_notes?: string;
}

// ============ Plan / Feature Types ============

export interface Plan {
  id: number;
  name: string;
  slug: string;
  price: number;
  listing_limit: number;
  feature_limit: number;
  is_featured: boolean;
  description?: string;
  duration_days: number;
}

export type SubscriptionStatus = 'active' | 'expired' | 'cancelled' | 'trialing';

export interface Subscription {
  id: number;
  user: number;
  plan: Plan;
  status: SubscriptionStatus;
  start_date: string;
  end_date: string;
  created_at: string;
}

export interface Feature {
  id: number;
  name: string;
  slug: string;
  description: string;
  icon: string | null;
  type: 'listing' | 'store' | 'promotion';
  price: number;
}

// ============ Escrow / Pay Link Types ============

export interface PayLink {
  id: number;
  seller: number;
  amount: number;
  description: string;
  reference: string;
  status: 'active' | 'paid' | 'expired' | 'cancelled';
  payment_url: string | null;
  expires_at: string;
  created_at: string;
}

export interface CreatePayLinkPayload {
  amount: number;
  description: string;
  expires_in?: number; // hours
}

// ============ Stats / Insights Types ============

export interface AdminStats {
  total_users: number;
  total_sellers: number;
  total_listings: number;
  total_orders: number;
  total_revenue: number;
  total_escrow_balance: number;
  pending_verifications: number;
  open_disputes: number;
  recent_users: User[];
  recent_orders: Order[];
}

export interface GrowthChartData {
  date: string;
  users: number;
  orders: number;
  revenue: number;
  listings: number;
}

export interface GrowthCharts {
  daily: GrowthChartData[];
  weekly: GrowthChartData[];
  monthly: GrowthChartData[];
}

export interface SellerStats {
  total_sales: number;
  total_revenue: number;
  total_orders: number;
  pending_orders: number;
  completed_orders: number;
  cancelled_orders: number;
  avg_rating: number;
  total_reviews: number;
  total_listings: number;
  active_listings: number;
  escrow_balance: number;
  pending_payouts: number;
  revenue_chart: Array<{ date: string; revenue: number; orders: number }>;
  order_status_breakdown: Record<string, number>;
  recent_orders: Order[];
}

export interface PlatformMetrics {
  total_gmv: number;
  total_commission: number;
  total_escrow_held: number;
  total_payouts_released: number;
  active_users_30d: number;
  conversion_rate: number;
  avg_order_value: number;
  top_categories: Array<{ category: string; count: number }>;
  top_sellers: Array<{ seller: string; revenue: number; orders: number }>;
}

export interface UserStats {
  total_users: number;
  active_users: number;
  new_users_today: number;
  new_users_week: number;
  new_users_month: number;
  verified_sellers: number;
  pending_verifications: number;
}

export interface PaymentMethodOption {
  id: string;
  name: string;
  type: PaymentMethod;
  channels: Array<{
    id: string;
    name: string;
    channel: PaymentChannel;
    icon: string | null;
  }>;
}

// ============ Error Types ============

export interface ApiError {
  status: number;
  message: string;
  detail?: string;
  errors?: Record<string, string[]>;
}

export class ApiClientError extends Error {
  status: number;
  detail: string;
  errors: Record<string, string[]>;

  constructor(error: ApiError) {
    super(error.message);
    this.name = 'ApiClientError';
    this.status = error.status;
    this.detail = error.detail || '';
    this.errors = error.errors || {};
  }
}

export type SupportRequestStatus = 'pending' | 'in_progress' | 'resolved' | 'closed';

export interface SupportRequest {
  id: number;
  user: number;
  subject: string;
  message: string;
  status: SupportRequestStatus;
  admin_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateSupportRequestPayload {
  subject: string;
  message: string;
}

export interface UpdateSupportRequestPayload {
  status?: SupportRequestStatus;
  admin_notes?: string;
}
