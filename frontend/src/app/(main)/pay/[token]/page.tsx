'use client';

import { GuestPayLinkPageView } from '../../view-modules';
export default function Page({ params }: { params: { token: string } }) {
  const { token } = params;
  return <GuestPayLinkPageView token={token} />;
}
