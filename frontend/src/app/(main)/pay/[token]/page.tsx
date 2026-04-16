'use client';

import { GuestPayLinkPageView } from '../../view-modules';
import { use } from 'react';

export default function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  return <GuestPayLinkPageView token={token} />;
}
