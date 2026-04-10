'use client';

import { use } from 'react';
import { CategoryPageView } from '../../view-modules';

export default function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  return <CategoryPageView categorySlug={slug} />;
}
