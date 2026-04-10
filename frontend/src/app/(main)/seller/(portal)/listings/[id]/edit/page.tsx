'use client';

import { use } from 'react';
import { SellerListingEditPageView } from '../../../../../view-modules';

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <SellerListingEditPageView listingId={id} />;
}
