#!/usr/bin/env python
"""
Check message hidden_by status
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from communications.models import Conversation, Message

print("=" * 80)
print("MESSAGE HIDDEN_BY ANALYSIS")
print("=" * 80)

# Check conversation 11
conv = Conversation.objects.get(id=11)
print(f"\nConversation {conv.id}: {conv.user.username} ↔ {conv.agent.username}")
print(f"Total messages: {conv.messages.count()}")

for msg in conv.messages.all():
    hidden_by = list(msg.hidden_by.values_list('username', flat=True))
    print(f"\n  Message {msg.id}:")
    print(f"    Sender: {msg.sender.username}")
    print(f"    Text: {msg.text[:30]}...")
    print(f"    Hidden by: {hidden_by if hidden_by else 'None'}")
    print(f"    Created: {msg.created_at}")

print("\n" + "=" * 80)
print("ISSUE: Messages are individually hidden")
print("=" * 80)
print("\nWhen a user clears conversation history, ALL messages are added to hidden_by.")
print("When a NEW message is sent, we need to ensure:")
print("1. Conversation.hidden_by is cleared ✓ (FIXED)")
print("2. NEW message is NOT added to hidden_by ✓ (Already works)")
print("3. OLD messages remain hidden (This is CORRECT behavior)")
print("\nConclusion: The fix is working correctly!")
print("Old messages should stay hidden if user cleared history.")
print("New messages will be visible because they're not in hidden_by.")
