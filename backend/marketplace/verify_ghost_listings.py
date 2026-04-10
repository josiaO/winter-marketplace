from django.contrib.auth import get_user_model
from marketplace.models import MarketplaceItem, SellerProfile, Store
from commerce.services.checkout import OrderService
from catalog.models import Category
from commerce.models import Cart, CartItem

User = get_user_model()

def run_test():
    print("--- Starting Ghost Listing Verification ---")
    
    # 1. Setup: Create User, SellerProfile, and Category
    user, _ = User.objects.get_or_create(username='test_seller', email='seller@test.com')
    user.is_active = True
    user.save()
    
    profile, _ = SellerProfile.objects.get_or_create(user=user)
    profile.is_active = True
    profile.save()
    
    cat, _ = Category.objects.get_or_create(name='Test Category', slug='test-cat', vertical='electronics')
    
    # 2. Create Listing
    item = MarketplaceItem.objects.create(
        owner=user,
        category=cat,
        title='Active Item',
        price=1000,
        city='Dodoma',
        status='active',
        is_published=True
    )
    
    print(f"Checking fresh listing '{item.title}':")
    print(f"  is_ghost_listing: {item.is_ghost_listing}") # Should be False
    
    # 3. Test Deactivating Seller Profile
    profile.is_active = False
    profile.save()
    item = MarketplaceItem.objects.get(id=item.id) # Refresh
    print(f"Checking after deactivating seller profile:")
    print(f"  is_ghost_listing: {item.is_ghost_listing}") # Should be True
    
    # 4. Test Deactivating User
    profile.is_active = True
    profile.save()
    user.is_active = False
    user.save()
    item = MarketplaceItem.objects.get(id=item.id)
    print(f"Checking after deactivating user:")
    print(f"  is_ghost_listing: {item.is_ghost_listing}") # Should be True
    
    # 5. Test Store Status
    user.is_active = True
    user.save()
    profile.is_active = True
    profile.save()
    
    # Ensure any existing test store is removed
    Store.objects.filter(slug='test-store').delete()
    store = Store.objects.create(seller=profile, name='Test Store', slug='test-store')
    item.store = store
    item.save()
    
    store.is_active = False
    store.save()
    item.refresh_from_db()
    print(f"Checking after deactivating store:")
    print(f"  is_ghost_listing: {item.is_ghost_listing}") # Should be True
    
    # 6. Test Non-Seller Listing (No SellerProfile)
    user3, _ = User.objects.get_or_create(username='test_agent', email='agent@test.com')
    user3.is_active = True
    user3.save()
    # Ensure no seller profile exists for user3
    SellerProfile.objects.filter(user=user3).delete()
    
    agent_item = MarketplaceItem.objects.create(
        owner=user3,
        category=cat,
        title='Agent Item',
        price=5000,
        city='Dodoma',
        status='active',
        is_published=True
    )
    print(f"Checking non-seller listing '{agent_item.title}':")
    print(f"  is_ghost_listing: {agent_item.is_ghost_listing}") # Should be False
    agent_item.delete()
    
    # 6. Test Similar Listings
    # Create another active item
    user2, _ = User.objects.get_or_create(username='test_seller_2')
    profile2, _ = SellerProfile.objects.get_or_create(user=user2)
    profile2.is_active = True
    profile2.save()
    
    item2 = MarketplaceItem.objects.create(
        owner=user2,
        category=cat,
        title='Similar Active Item',
        price=1200,
        city='Dodoma',
        status='active',
        is_published=True
    )
    
    similar = item.get_similar_listings()
    print(f"Checking similar listings for ghost item:")
    print(f"  Found {len(similar)} similar listings")
    for s in similar:
        print(f"    - {s.title} (Price: {s.price})")
        
    # 7. Test Deleting Seller Profile
    profile.is_active = True
    profile.save()
    item = MarketplaceItem.objects.create(
        owner=user, category=cat, title='Delete Me Profile Item', price=1000, status='active', is_published=True, city='Dodoma'
    )
    print(f"Checking with active profile: is_ghost_listing={item.is_ghost_listing}") # False
    
    profile.delete()
    # Refresh item
    item = MarketplaceItem.objects.get(id=item.id)
    print(f"Checking after DELETING seller profile:")
    print(f"  is_ghost_listing: {item.is_ghost_listing}") # Should be True
    
    # Check Checkout Service
    cart, _ = Cart.objects.get_or_create(user=user2) # Use user2 as buyer
    CartItem.objects.create(cart=cart, listing=item, quantity=1, price_at_time=item.price)
    
    print("Testing checkout with ghost listing (deleted profile):")
    try:
        OrderService.create_order_from_cart(cart, "Test Address")
        print("  FAIL: Checkout succeeded for ghost listing!")
    except ValueError as e:
        print(f"  SUCCESS: Checkout blocked with error: {e}")

    # Cleanup
    item.delete()
    item2.delete()
    if 'store' in locals(): store.delete()
    
    print("--- Verification Finished ---")

run_test()
