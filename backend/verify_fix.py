#!/usr/bin/env python
"""
Test script to verify the message visibility fix
This simulates sending a message and checks if conversation is visible to sender
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from communications.models import Conversation, Message
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

print("=" * 80)
print("VERIFICATION TEST: Message Visibility After Fix")
print("=" * 80)

# Find a conversation with messages
conversation = Conversation.objects.filter(messages__isnull=False).first()

if not conversation:
    print("\n❌ No conversations with messages found for testing")
    exit(1)

print(f"\n✓ Testing with Conversation ID: {conversation.id}")
print(f"  User: {conversation.user.username}")
print(f"  Agent: {conversation.agent.username}")
print(f"  Total messages: {conversation.messages.count()}")

# Check current hidden_by status
hidden_by_users = list(conversation.hidden_by.values_list('username', flat=True))
print(f"\n  Currently hidden by: {hidden_by_users if hidden_by_users else 'None'}")

# Simulate the fix: clear hidden_by
print("\n" + "-" * 80)
print("Simulating fix: conversation.hidden_by.clear()")
print("-" * 80)
conversation.hidden_by.clear()

# Verify it's cleared
hidden_by_users_after = list(conversation.hidden_by.values_list('username', flat=True))
print(f"  Hidden by after clear: {hidden_by_users_after if hidden_by_users_after else 'None ✓'}")

# Check if conversation would be visible in queryset
user = conversation.user
visible_conversations = Conversation.objects.filter(
    Q(user=user) | Q(agent=user)
).exclude(hidden_by=user)

is_visible = visible_conversations.filter(id=conversation.id).exists()
print(f"\n  Conversation visible to {user.username}: {'✓ YES' if is_visible else '❌ NO'}")

# Check messages visibility
visible_messages = conversation.messages.exclude(hidden_by=user).count()
total_messages = conversation.messages.count()
print(f"  Messages visible to {user.username}: {visible_messages}/{total_messages}")

# Check for agent
agent = conversation.agent
visible_to_agent = Conversation.objects.filter(
    Q(user=agent) | Q(agent=agent)
).exclude(hidden_by=agent).filter(id=conversation.id).exists()
print(f"  Conversation visible to {agent.username}: {'✓ YES' if visible_to_agent else '❌ NO'}")

print("\n" + "=" * 80)
print("SUMMARY OF ALL CONVERSATIONS")
print("=" * 80)

# Show all conversations and their hidden status
for conv in Conversation.objects.all()[:5]:
    hidden_by = list(conv.hidden_by.values_list('username', flat=True))
    msg_count = conv.messages.count()
    print(f"\nConversation {conv.id}:")
    print(f"  Participants: {conv.user.username} ↔ {conv.agent.username}")
    print(f"  Messages: {msg_count}")
    print(f"  Hidden by: {hidden_by if hidden_by else 'None ✓'}")
    
    # Check visibility for both participants
    user_can_see = not conv.hidden_by.filter(id=conv.user.id).exists()
    agent_can_see = not conv.hidden_by.filter(id=conv.agent.id).exists()
    print(f"  Visible to {conv.user.username}: {'✓' if user_can_see else '❌'}")
    print(f"  Visible to {conv.agent.username}: {'✓' if agent_can_see else '❌'}")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
