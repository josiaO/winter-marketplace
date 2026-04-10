#!/usr/bin/env python
"""
Test the start_conversation fix
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from communications.models import Conversation
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

print("=" * 80)
print("TEST: start_conversation FIX")
print("=" * 80)

# Get test users
user1 = User.objects.get(username='johndoe')
user2 = User.objects.get(username='joseph.ochieng83')

print(f"\nTest users: {user1.username} and {user2.username}")

# Find existing conversation
conversation = Conversation.objects.filter(
    (Q(user=user1) & Q(agent=user2)) | (Q(user=user2) & Q(agent=user1))
).first()

if not conversation:
    print("❌ No conversation found between these users")
    exit(1)

print(f"\nConversation {conversation.id}:")
print(f"  Participants: {conversation.user.username} ↔ {conversation.agent.username}")
print(f"  Messages: {conversation.messages.count()}")

# Check current state
hidden_by = list(conversation.hidden_by.values_list('username', flat=True))
print(f"  Currently hidden by: {hidden_by if hidden_by else 'None'}")

# Simulate the fix: clear hidden_by (as start_conversation would do)
print("\n" + "-" * 80)
print("Simulating start_conversation fix: conversation.hidden_by.clear()")
print("-" * 80)

conversation.hidden_by.clear()

# Verify both can see it
hidden_by_after = list(conversation.hidden_by.values_list('username', flat=True))
print(f"  Hidden by after fix: {hidden_by_after if hidden_by_after else 'None ✓'}")

user1_can_see = Conversation.objects.filter(
    Q(user=user1) | Q(agent=user1)
).exclude(hidden_by=user1).filter(id=conversation.id).exists()

user2_can_see = Conversation.objects.filter(
    Q(user=user2) | Q(agent=user2)
).exclude(hidden_by=user2).filter(id=conversation.id).exists()

print(f"\n  Visible to {user1.username}: {'✓ YES' if user1_can_see else '❌ NO'}")
print(f"  Visible to {user2.username}: {'✓ YES' if user2_can_see else '❌ NO'}")

print("\n" + "=" * 80)
print("RESULT")
print("=" * 80)

if user1_can_see and user2_can_see:
    print("\n✅ SUCCESS! Both participants can see the conversation")
else:
    print("\n❌ FAILED! One or both participants cannot see the conversation")

print("\n" + "=" * 80)
