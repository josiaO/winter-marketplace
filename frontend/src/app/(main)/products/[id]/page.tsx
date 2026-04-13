'use client';

import { ProductPageView } from '../../view-modules';

export default function Page({ params }: { params: { id: string } }) {
  const { id } = params;
  return <ProductPageView productId={id} />;
}
