'use client';

import { ConversationPageView } from '../../view-modules';

export default function Page({
  params,
}: {
  params: { conversationId: string };
}) {
  const { conversationId } = params;
  return <ConversationPageView conversationId={conversationId} />;
}
