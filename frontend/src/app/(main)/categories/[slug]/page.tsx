'use client';

import { CategoryPageView } from '../../view-modules';
export default function Page({ params }: { params: { slug: string } }) {
  const { slug } = params;
  return <CategoryPageView categorySlug={slug} />;
}
