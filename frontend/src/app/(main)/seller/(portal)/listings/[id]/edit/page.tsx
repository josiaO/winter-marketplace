'use client';

import { SellerListingEditPageView } from '../../../../../view-modules';
export default function Page({ params }: { params: { id: string } }) {
  const { id } = params;
  return <SellerListingEditPageView listingId={id} />;
}
