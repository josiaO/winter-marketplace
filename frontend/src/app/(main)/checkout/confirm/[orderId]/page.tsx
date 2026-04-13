'use client';

import { PaymentConfirmationPageView } from '../../../view-modules';
import { use } from 'react';

export default function Page({ params }: { params: Promise<{ orderId: string }> }) {
  const { orderId } = use(params);
  return <PaymentConfirmationPageView orderId={orderId} />;
}
