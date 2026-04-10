'use client';

import { use } from 'react';
import { CheckoutSuccessPageView } from '../../../view-modules';

export default function Page({ params }: { params: Promise<{ orderId: string }> }) {
  const { orderId } = use(params);
  return <CheckoutSuccessPageView orderId={orderId} />;
}
