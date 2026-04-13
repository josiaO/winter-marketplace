'use client';

import { SellerProfilePageView } from '../../view-modules';
import { use } from 'react';

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <SellerProfilePageView sellerId={id} />;
}
