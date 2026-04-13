/**
 * Canonical FCM payloads for seller notifications (Swahili + English).
 * Backend should send `data` + `notification` per seller language preference (`sw` | `en`).
 */

export type SellerNotificationLang = 'sw' | 'en';

export const SELLER_PUSH_TRIGGERS = {
  NEW_ORDER: 'new_order',
  PAYMENT_CONFIRMED: 'payment_confirmed',
  FUNDS_RELEASED: 'funds_released',
  DISPUTE_OPENED: 'dispute_opened',
  NEW_REVIEW: 'new_review',
  LOW_STOCK: 'low_stock',
} as const;

export type SellerPushTrigger = (typeof SELLER_PUSH_TRIGGERS)[keyof typeof SELLER_PUSH_TRIGGERS];

const SW = {
  newOrderTitle: '🛒 Agizo Jipya!',
  paymentTitle: '💰 Malipo Yamepokelewa',
  fundsTitle: '✅ Pesa Zimeachiwa!',
  disputeTitle: '⚠️ Mnunuzi Amefungua Mgogoro',
  reviewTitle: '⭐ Tathmini Mpya',
  lowStockTitle: '📦 Bidhaa Karibu Kwisha',
} as const;

const EN = {
  newOrderTitle: '🛒 New order!',
  paymentTitle: '💰 Payment received',
  fundsTitle: '✅ Funds released!',
  disputeTitle: '⚠️ Buyer opened a dispute',
  reviewTitle: '⭐ New review',
  lowStockTitle: '📦 Low stock alert',
} as const;

export function sellerPushCopy(
  trigger: SellerPushTrigger,
  lang: SellerNotificationLang,
  vars: {
    buyerName?: string;
    productName?: string;
    amount?: string;
    orderId?: string | number;
    rating?: number;
    count?: number;
    productId?: string | number;
  },
): { title: string; body: string; deepLink: string; sound: 'default' | 'alert' } {
  const sw = lang === 'sw';
  const b = vars.buyerName ?? 'Buyer';
  const p = vars.productName ?? 'item';
  const amt = vars.amount ?? '';
  const oid = vars.orderId ?? '';
  const rid = vars.rating ?? 0;
  const cnt = vars.count ?? 0;
  const pid = vars.productId ?? '';

  switch (trigger) {
    case SELLER_PUSH_TRIGGERS.NEW_ORDER:
      return {
        title: sw ? SW.newOrderTitle : EN.newOrderTitle,
        body: sw
          ? `${b} amenunua ${p} — ${amt}`
          : `${b} purchased ${p} — ${amt}`,
        deepLink: `/seller/orders/${encodeURIComponent(String(oid))}`,
        sound: 'default',
      };
    case SELLER_PUSH_TRIGGERS.PAYMENT_CONFIRMED:
      return {
        title: sw ? SW.paymentTitle : EN.paymentTitle,
        body: sw
          ? `${amt} iko salama kwenye escrow. Tuma ${p} kwa ${b}.`
          : `${amt} is held in escrow. Ship ${p} to ${b}.`,
        deepLink: `/seller/orders/${encodeURIComponent(String(oid))}`,
        sound: 'default',
      };
    case SELLER_PUSH_TRIGGERS.FUNDS_RELEASED:
      return {
        title: sw ? SW.fundsTitle : EN.fundsTitle,
        body: sw
          ? `${amt} sasa iko tayari kuondoa. Agizo #${oid} limekamilika.`
          : `${amt} is ready to withdraw. Order #${oid} is complete.`,
        deepLink: '/seller/wallet',
        sound: 'default',
      };
    case SELLER_PUSH_TRIGGERS.DISPUTE_OPENED:
      return {
        title: sw ? SW.disputeTitle : EN.disputeTitle,
        body: sw
          ? `${b} hana furaha na agizo #${oid}. Angalia na ujibu haraka.`
          : `${b} opened a dispute on order #${oid}. Review and respond quickly.`,
        deepLink: `/seller/orders/${encodeURIComponent(String(oid))}/dispute`,
        sound: 'alert',
      };
    case SELLER_PUSH_TRIGGERS.NEW_REVIEW:
      return {
        title: sw ? SW.reviewTitle : EN.reviewTitle,
        body: sw
          ? `${b} amekupa nyota ${rid}/5`
          : `${b} rated you ${rid}/5 stars`,
        deepLink: '/seller/reviews',
        sound: 'default',
      };
    case SELLER_PUSH_TRIGGERS.LOW_STOCK:
      return {
        title: sw ? SW.lowStockTitle : EN.lowStockTitle,
        body: sw
          ? `${p} imebaki ${cnt} tu. Ongeza stoki sasa.`
          : `${p} has only ${cnt} left. Restock now.`,
        deepLink: `/seller/listings/${encodeURIComponent(String(pid))}/edit`,
        sound: 'default',
      };
    default:
      return { title: EN.newOrderTitle, body: '', deepLink: '/seller/dashboard', sound: 'default' };
  }
}
