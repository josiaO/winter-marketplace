#!/usr/bin/env python
"""
Debug script to check new conversation creation flow
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
print("NEW CONVERSATION VISIBILITY DEBUG")
print("=" * 80)

# Get all conversations
all_convs = Conversation.objects.all().order_by('-created_at')[:10]

print(f"\nTotal conversations: {Conversation.objects.count()}")
print(f"\nRecent conversations (last 10):")

for conv in all_convs:
    hidden_by = list(conv.hidden_by.values_list('username', flat=True))
    msg_count = conv.messages.count()
    
    print(f"\n{'='*60}")
    print(f"Conversation {conv.id}:")
    print(f"  User: {conv.user.username} (ID: {conv.user.id})")
    print(f"  Agent: {conv.agent.username} (ID: {conv.agent.id})")
    print(f"  Property: {conv.property.title if conv.property else 'None'}")
    print(f"  Created: {conv.created_at}")
    print(f"  Updated: {conv.updated_at}")
    print(f"  Messages: {msg_count}")
    print(f"  Hidden by: {hidden_by if hidden_by else 'None ✓'}")
    
    # Check visibility for both participants
    user_can_see = Conversation.objects.filter(
        Q(user=conv.user) | Q(agent=conv.user)
    ).exclude(hidden_by=conv.user).filter(id=conv.id).exists()
    
    agent_can_see = Conversation.objects.filter(
        Q(user=conv.agent) | Q(agent=conv.agent)
    ).exclude(hidden_by=conv.agent).filter(id=conv.id).exists()
    
    print(f"  Visible to {conv.user.username}: {'✓ YES' if user_can_see else '❌ NO'}")
    print(f"  Visible to {conv.agent.username}: {'✓ YES' if agent_can_see else '❌ NO'}")
    
    # Show messages
    if msg_count > 0:
        print(f"\n  Messages:")
        for msg in conv.messages.all()[:3]:
            msg_hidden = list(msg.hidden_by.values_list('username', flat=True))
            print(f"    - [{msg.sender.username}] {msg.text[:40]}... (hidden: {msg_hidden or 'None'})")

print("\n" + "=" * 80)
print("CHECKING FOR CONVERSATIONS WITH NO MESSAGES")
print("=" * 80)

empty_convs = Conversation.objects.filter(messages__isnull=True)
print(f"\nConversations with 0 messages: {empty_convs.count()}")

for conv in empty_convs[:5]:
    hidden_by = list(conv.hidden_by.values_list('username', flat=True))
    print(f"\nConversation {conv.id}:")
    print(f"  Participants: {conv.user.username} ↔ {conv.agent.username}")
    print(f"  Created: {conv.created_at}")
    print(f"  Hidden by: {hidden_by if hidden_by else 'None ✓'}")
    
    user_can_see = not conv.hidden_by.filter(id=conv.user.id).exists()
    agent_can_see = not conv.hidden_by.filter(id=conv.agent.id).exists()
    
    print(f"  Visible to {conv.user.username}: {'✓' if user_can_see else '❌'}")
    print(f"  Visible to {conv.agent.username}: {'✓' if agent_can_see else '❌'}")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
