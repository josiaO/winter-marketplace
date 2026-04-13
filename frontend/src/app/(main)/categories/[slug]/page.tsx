'use client';

import { CategoryPageView } from '../../view-modules';
import { use } from 'react';

export default function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  return <CategoryPageView categorySlug={slug} />;
}
