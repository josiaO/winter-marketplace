'use client';

import { StorePageView } from '../../view-modules';

export default function Page({ params }: { params: { slug: string } }) {
  const { slug } = params;
  return <StorePageView storeSlug={slug} />;
}
