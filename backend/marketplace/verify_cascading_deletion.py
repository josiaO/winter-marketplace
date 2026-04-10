import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from marketplace.models import SellerProfile, Store, MarketplaceItem
from marketplace.serializers import MarketplaceItemSerializer
from catalog.models import Category
from rest_framework import serializers

User = get_user_model()

def verify_cascading_and_store():
    print("--- Starting Verification: Cascading Deletion and Store Requirement ---")
    
    # 1. Setup
    username = "test_cascading_user"
    User.objects.filter(username=username).delete()
    user = User.objects.create_user(username=username, password="password123")
    
    # Create category
    cat, _ = Category.objects.get_or_create(name="Test Category", slug="test-cat")
    leaf_cat, _ = Category.objects.get_or_create(name="Leaf Category", slug="leaf-cat", parent=cat)
    
    print(f"Created user: {user.username}")
    
    # 2. Test Store Requirement (Failure Case)
    print("\nTesting: Listing without a SellerProfile and Store (Should fail)")
    serializer = MarketplaceItemSerializer(data={
        'title': 'Test Item',
        'description': 'Test Desc',
        'price': '100.00',
        'category': leaf_cat.id,
        'city': 'Dodoma',
        'status': 'active'
    }, context={'request': type('obj', (object,), {'user': user})()})
    
    try:
        serializer.is_valid(raise_exception=True)
        print("❌ Error: Managed to validate listing without a SellerProfile!")
    except serializers.ValidationError as e:
        print(f"✅ Success: Blocked listing without profile/store. Error: {e}")

    # 3. Create SellerProfile but NO Store
    profile = SellerProfile.objects.create(user=user, business_name="Test Business", is_active=True)
    print(f"\nCreated SellerProfile for {user.username}")
    
    print("Testing: Listing with SellerProfile but NO Store (Should fail)")
    serializer = MarketplaceItemSerializer(data={
        'title': 'Test Item',
        'description': 'Test Desc',
        'price': '100.00',
        'category': leaf_cat.id,
        'city': 'Dodoma',
        'status': 'active'
    }, context={'request': type('obj', (object,), {'user': user})()})
    
    try:
        serializer.is_valid(raise_exception=True)
        print("❌ Error: Managed to validate listing without a Store!")
    except serializers.ValidationError as e:
        print(f"✅ Success: Blocked listing without store. Error: {e}")

    # 4. Create Store and Test Listing (Success Case)
    store = Store.objects.create(seller=profile, name="Test Store", slug="test-store", is_active=True)
    print(f"\nCreated active store: {store.name}")
    
    print("Testing: Listing with active Store (Should succeed and auto-assign)")
    serializer = MarketplaceItemSerializer(data={
        'title': 'Test Item',
        'description': 'Test Desc',
        'price': '100.00',
        'category': leaf_cat.id,
        'city': 'Dodoma',
        'status': 'active'
    }, context={'request': type('obj', (object,), {'user': user})()})
    
    if serializer.is_valid():
        print("✅ Success: Listing is valid with active store.")
        item = serializer.save(owner=user)
        print(f"Created item: {item.title}, Assigned store: {item.store.name}")
    else:
        print(f"❌ Error: Validation failed. Errors: {serializer.errors}")
        return

    # 5. Test Cascading Deletion
    item_id = item.id
    store_id = store.id
    print(f"\nTesting: Cascading deletion. Deleting SellerProfile (id={profile.id})...")
    profile.delete()
    
    # Check if store is deleted
    store_exists = Store.objects.filter(id=store_id).exists()
    print(f"Store exists after profile deletion: {store_exists}")
    
    # Check if item is deleted
    item_exists = MarketplaceItem.objects.filter(id=item_id).exists()
    print(f"MarketplaceItem exists after profile deletion: {item_exists}")
    
    if not store_exists and not item_exists:
        print("✅ Final Success: Deleting SellerProfile correctly cascaded to delete the Store and the Item!")
    else:
        print("❌ Final Failure: Cascading deletion did not work as expected.")

if __name__ == "__main__":
    verify_cascading_and_store()
