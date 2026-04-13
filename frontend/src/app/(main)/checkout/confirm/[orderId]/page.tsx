'use client';

import { PaymentConfirmationPageView } from '../../../view-modules';

export default function Page({ params }: { params: { orderId: string } }) {
  const { orderId } = params;
  return <PaymentConfirmationPageView orderId={orderId} />;
}
