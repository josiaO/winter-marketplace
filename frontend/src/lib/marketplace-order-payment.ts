/**
 * Maps marketplace Order + escrow snapshot to buyer payment UI.
 *
 * Backend reference:
 * - Checkout creates `Order(status=pending)` and an escrow `Transaction` (see
 *   `commerce/services/checkout.py` + `escrow_engine` create_transaction).
 * - Online payment: after provider verify, `confirm_payment` moves txn toward
 *   HOLD; `commerce/services/order_escrow_sync.sync_marketplace_order_on_escrow_hold`
 *   sets `Order.status='confirmed'` when funds reach HOLD.
 * - `OrderSerializer.get_escrow` exposes `escrow.status` as
 *   `escrow_engine.state_machine.TransactionStatus` strings (uppercase:
 *   CREATED, PENDING_PAYMENT, PAID, HOLD, FAILED, …).
 * - Offline checkout (`cash_on_delivery`, `cod`, …) skips hosted gateway
 *   (`escrow_engine/providers/registry.should_open_payment_gateway`).
 */
import type { Order } from '@/types/api';

/** Same set as registry._OFFLINE_CHECKOUT_METHODS (lowercase, hyphen → underscore). */
const OFFLINE_PAYMENT_KEYS = new Set([
  'manual',
  'cash_on_delivery',
  'cod',
  'pay_at_pickup',
  'invoice',
  'offline',
]);

function normalizeMethodKey(method: string | undefined | null): string {
  return (method || '').toLowerCase().replace(/-/g, '_').trim();
}

export function isOfflineCheckoutPaymentMethod(
  method: string | undefined | null,
): boolean {
  const k = normalizeMethodKey(method);
  if (!k) return false;
  return OFFLINE_PAYMENT_KEYS.has(k);
}

export type OrderEscrowSnapshot = {
  status?: string;
  payment_method?: string;
} | null;

export type OrderWithEscrow = Order & { escrow?: OrderEscrowSnapshot };

function paymentMethodForOrder(order: OrderWithEscrow): string {
  return (
    order.payment_method ||
    order.escrow?.payment_method ||
    ''
  );
}

/**
 * True when escrow funds are held or past payment (buyer should not open gateway).
 * Aligns with `payment-confirmation` “secured” messaging.
 */
export function escrowFundsSecured(order: OrderWithEscrow): boolean {
  const s = order.escrow?.status;
  if (!s) return false;
  return ['HOLD', 'RELEASED', 'REFUNDED', 'DISPUTED'].includes(s);
}

/**
 * Show “Complete payment” / payment-confirmation entry points for the buyer.
 * Uses `order.escrow.status` (API), not legacy `order.transaction` typing.
 */
export function buyerShouldSeeOnlinePaymentCta(order: OrderWithEscrow): boolean {
  if (isOfflineCheckoutPaymentMethod(paymentMethodForOrder(order))) {
    return false;
  }
  if (
    order.status === 'cancelled' ||
    order.status === 'refunded' ||
    order.status === 'completed' ||
    order.status === 'disputed'
  ) {
    return false;
  }
  if (
    ['shipped', 'arrived', 'delivered'].includes(order.status)
  ) {
    return false;
  }

  if (escrowFundsSecured(order)) return false;

  const es = order.escrow?.status;
  if (es === 'FAILED' || es === 'CANCELLED') return true;

  if (
    order.status === 'pending' ||
    order.status === 'confirmed' ||
    order.status === 'processing'
  ) {
    return true;
  }

  return false;
}
