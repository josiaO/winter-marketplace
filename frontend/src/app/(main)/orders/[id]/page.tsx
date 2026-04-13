'use client';

import { OrderDetailPageView } from '../../view-modules';

export default function Page({ params }: { params: { id: string } }) {
  const { id } = params;
  return <OrderDetailPageView orderId={id} />;
}
