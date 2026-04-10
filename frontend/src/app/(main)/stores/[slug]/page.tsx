'use client';

import { use } from 'react';
import { StorePageView } from '../../view-modules';

export default function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  return <StorePageView storeSlug={slug} />;
}
