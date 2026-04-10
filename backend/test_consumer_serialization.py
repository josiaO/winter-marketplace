
import os
import django
import asyncio
from channels.db import database_sync_to_async
from unittest.mock import MagicMock

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from communications.models import Message, Conversation
from communications.consumers import ChatConsumer
from django.contrib.auth import get_user_model
from properties.models import Property, MediaProperty

User = get_user_model()

async def test_serialization():
    # Setup
    user = await database_sync_to_async(User.objects.first)()
    if not user:
        print("No user found, can't test")
        return

    # Mock consumer
    consumer = ChatConsumer()
    consumer.user = user
    consumer.scope = {'user': user}

    # Create dummy property if needed
    prop = await database_sync_to_async(Property.objects.first)()
    if not prop:
        print("No property found. Skipping property test.")
    
    # Create dummy message with property
    msg = await database_sync_to_async(Message.objects.create)(
        sender=user,
        text="Test message",
        conversation_id=1, # Needs valid ID or mock
        property_attachment=prop
    )

    try:
        # Test serialization
        data = await consumer.serialize_message(msg)
        print("\nSerialized Data:")
        print(data)
        
        # Verify property attachment structure
        if prop:
            assert data['property_attachment'] is not None
            assert 'title' in data['property_attachment']
            assert 'primary_image' in data['property_attachment']
            print("\n✅ Property attachment serialization confirmed.")
        
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
    finally:
        # Cleanup
        await database_sync_to_async(msg.delete)()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test_serialization())
