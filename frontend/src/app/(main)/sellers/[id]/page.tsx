'use client';

import { use } from 'react';
import { SellerProfilePageView } from '../../view-modules';

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <SellerProfilePageView sellerId={id} />;
}
