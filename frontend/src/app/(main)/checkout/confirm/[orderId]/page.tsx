'use client';

import { use } from 'react';
import { PaymentConfirmationPageView } from '../../../view-modules';

export default function Page({ params }: { params: Promise<{ orderId: string }> }) {
  const { orderId } = use(params);
  return <PaymentConfirmationPageView orderId={orderId} />;
}
