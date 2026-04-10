'use client';

import { use } from 'react';
import { ConversationPageView } from '../../view-modules';

export default function Page({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = use(params);
  return <ConversationPageView conversationId={conversationId} />;
}
