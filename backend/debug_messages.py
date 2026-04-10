#!/usr/bin/env python
"""
Debug script to verify message persistence in database
Run: python manage.py shell < debug_messages.py
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
print("STEP 1: DATABASE VERIFICATION")
print("=" * 80)

# Check total conversations
total_conversations = Conversation.objects.count()
print(f"\n✓ Total Conversations in DB: {total_conversations}")

# Check total messages
total_messages = Message.objects.count()
print(f"✓ Total Messages in DB: {total_messages}")

# Show recent conversations
print("\n" + "-" * 80)
print("Recent Conversations (last 5):")
print("-" * 80)
for conv in Conversation.objects.all().order_by('-updated_at')[:5]:
    msg_count = conv.messages.count()
    print(f"\nConversation ID: {conv.id}")
    print(f"  User: {conv.user.username} (ID: {conv.user.id})")
    print(f"  Agent: {conv.agent.username} (ID: {conv.agent.id})")
    print(f"  Property: {conv.property.title if conv.property else 'None'}")
    print(f"  Messages: {msg_count}")
    print(f"  Created: {conv.created_at}")
    print(f"  Updated: {conv.updated_at}")
    print(f"  Is Active: {conv.is_active}")
    print(f"  Hidden by: {list(conv.hidden_by.values_list('username', flat=True))}")

# Show recent messages
print("\n" + "-" * 80)
print("Recent Messages (last 10):")
print("-" * 80)
for msg in Message.objects.all().order_by('-created_at')[:10]:
    print(f"\nMessage ID: {msg.id}")
    print(f"  Conversation: {msg.conversation.id}")
    print(f"  Sender: {msg.sender.username} (ID: {msg.sender.id})")
    print(f"  Text: {msg.text[:50]}..." if len(msg.text) > 50 else f"  Text: {msg.text}")
    print(f"  Status: {msg.status}")
    print(f"  Created: {msg.created_at}")
    print(f"  Read at: {msg.read_at}")
    print(f"  Is Deleted: {msg.is_deleted}")
    print(f"  Hidden by: {list(msg.hidden_by.values_list('username', flat=True))}")

# Check for messages that might be hidden
print("\n" + "-" * 80)
print("Messages with hidden_by relationships:")
print("-" * 80)
hidden_messages = Message.objects.exclude(hidden_by__isnull=True).distinct()
print(f"Total hidden messages: {hidden_messages.count()}")
for msg in hidden_messages[:5]:
    print(f"  Message {msg.id}: hidden by {list(msg.hidden_by.values_list('username', flat=True))}")

# Check for specific user's conversations
print("\n" + "-" * 80)
print("Per-User Analysis:")
print("-" * 80)
for user in User.objects.all()[:3]:
    user_convs = Conversation.objects.filter(Q(user=user) | Q(agent=user))
    user_msgs = Message.objects.filter(conversation__in=user_convs)
    print(f"\nUser: {user.username} (ID: {user.id})")
    print(f"  Conversations: {user_convs.count()}")
    print(f"  Messages: {user_msgs.count()}")
    print(f"  Hidden conversations: {user.hidden_conversations.count()}")
    print(f"  Hidden messages: {user.hidden_messages.count()}")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
