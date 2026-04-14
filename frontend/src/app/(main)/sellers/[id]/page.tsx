'use client';

import { SellerProfilePageView } from '../../view-modules';
export default function Page({ params }: { params: { id: string } }) {
  const { id } = params;
  return <SellerProfilePageView sellerId={id} />;
}
