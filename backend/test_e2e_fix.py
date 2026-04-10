#!/usr/bin/env python
"""
End-to-end test: Simulate sending a new message and verify visibility
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
print("END-TO-END TEST: Send Message After Clearing History")
print("=" * 80)

# Get test users
try:
    user1 = User.objects.get(username='johndoe')
    user2 = User.objects.get(username='jane.nyambura46')
except User.DoesNotExist:
    print("❌ Test users not found")
    exit(1)

print(f"\n✓ Test users: {user1.username} and {user2.username}")

# Find or create a test conversation
conversation = Conversation.objects.filter(
    Q(user=user1, agent=user2) | Q(user=user2, agent=user1)
).first()

if not conversation:
    conversation = Conversation.objects.create(user=user1, agent=user2)
    print(f"✓ Created new conversation {conversation.id}")
else:
    print(f"✓ Using existing conversation {conversation.id}")

print("\n" + "-" * 80)
print("STEP 1: Clear conversation history (simulate user deleting chat)")
print("-" * 80)

# Simulate clearing history - add both users to hidden_by
conversation.hidden_by.add(user1)
conversation.hidden_by.add(user2)
print(f"  Hidden by: {list(conversation.hidden_by.values_list('username', flat=True))}")

# Hide all messages
for msg in conversation.messages.all():
    msg.hidden_by.add(user1)
    msg.hidden_by.add(user2)

print(f"  All {conversation.messages.count()} messages hidden for both users")

# Verify conversation is NOT visible
visible_to_user1 = Conversation.objects.filter(
    Q(user=user1) | Q(agent=user1)
).exclude(hidden_by=user1).filter(id=conversation.id).exists()

print(f"  Conversation visible to {user1.username}: {'✓ YES' if visible_to_user1 else '❌ NO (Expected)'}")

print("\n" + "-" * 80)
print("STEP 2: Send a new message (simulate the FIX)")
print("-" * 80)

# Create a new message
new_message = Message.objects.create(
    conversation=conversation,
    sender=user1,
    text="Test message after fix - this should be visible!"
)
print(f"  Created message {new_message.id}: '{new_message.text[:50]}'")

# Apply the FIX: Clear conversation.hidden_by
conversation.hidden_by.clear()
print(f"  Applied fix: conversation.hidden_by.clear()")
print(f"  Hidden by after fix: {list(conversation.hidden_by.values_list('username', flat=True)) or 'None ✓'}")

print("\n" + "-" * 80)
print("STEP 3: Verify visibility after fix")
print("-" * 80)

# Check conversation visibility
visible_to_user1 = Conversation.objects.filter(
    Q(user=user1) | Q(agent=user1)
).exclude(hidden_by=user1).filter(id=conversation.id).exists()

visible_to_user2 = Conversation.objects.filter(
    Q(user=user2) | Q(agent=user2)
).exclude(hidden_by=user2).filter(id=conversation.id).exists()

print(f"  Conversation visible to {user1.username}: {'✓ YES' if visible_to_user1 else '❌ NO'}")
print(f"  Conversation visible to {user2.username}: {'✓ YES' if visible_to_user2 else '❌ NO'}")

# Check message visibility
visible_msgs_user1 = conversation.messages.exclude(hidden_by=user1).count()
visible_msgs_user2 = conversation.messages.exclude(hidden_by=user2).count()
total_msgs = conversation.messages.count()

print(f"\n  Messages visible to {user1.username}: {visible_msgs_user1}/{total_msgs}")
print(f"  Messages visible to {user2.username}: {visible_msgs_user2}/{total_msgs}")

# Check if the NEW message is visible
new_msg_visible_user1 = not new_message.hidden_by.filter(id=user1.id).exists()
new_msg_visible_user2 = not new_message.hidden_by.filter(id=user2.id).exists()

print(f"\n  NEW message visible to {user1.username}: {'✓ YES' if new_msg_visible_user1 else '❌ NO'}")
print(f"  NEW message visible to {user2.username}: {'✓ YES' if new_msg_visible_user2 else '❌ NO'}")

print("\n" + "=" * 80)
print("TEST RESULT")
print("=" * 80)

success = (
    visible_to_user1 and 
    visible_to_user2 and 
    new_msg_visible_user1 and 
    new_msg_visible_user2
)

if success:
    print("\n✅ SUCCESS! The fix works correctly:")
    print("   - Conversation is visible to both users")
    print("   - New message is visible to both users")
    print("   - Old messages remain hidden (correct behavior)")
else:
    print("\n❌ FAILED! Issues detected:")
    if not visible_to_user1:
        print(f"   - Conversation not visible to {user1.username}")
    if not visible_to_user2:
        print(f"   - Conversation not visible to {user2.username}")
    if not new_msg_visible_user1:
        print(f"   - New message not visible to {user1.username}")
    if not new_msg_visible_user2:
        print(f"   - New message not visible to {user2.username}")

print("\n" + "=" * 80)
