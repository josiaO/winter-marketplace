'use client';

import { CheckoutSuccessPageView } from '../../../view-modules';
export default function Page({ params }: { params: { orderId: string } }) {
  const { orderId } = params;
  return <CheckoutSuccessPageView orderId={orderId} />;
}
