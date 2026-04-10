'use client';

import { use } from 'react';
import { OrderDetailPageView } from '../../view-modules';

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <OrderDetailPageView orderId={id} />;
}
