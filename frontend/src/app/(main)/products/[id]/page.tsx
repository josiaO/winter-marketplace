'use client';

import { use } from 'react';
import { ProductPageView } from '../../view-modules';

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <ProductPageView productId={id} />;
}
