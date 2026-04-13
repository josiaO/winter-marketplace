'use client';

import { ConversationPageView } from '../../view-modules';
import { use } from 'react';

export default function Page({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = use(params);
  return <ConversationPageView conversationId={conversationId} />;
}
