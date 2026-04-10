"""
Debug script to test ghost listing logic
Run: python manage.py shell < debug_ghost_listing.py
"""
from listings.models import Listing
from accounts.models import User
from marketplace.models import SellerProfile

# Find an active seller with a listing
active_seller = User.objects.filter(is_active=True).first()
if not active_seller:
    print("No active seller found")
    exit()

print(f"\n=== Testing with seller: {active_seller.username} ===")
print(f"Seller is_active: {active_seller.is_active}")

# Check seller profile
try:
    profile = active_seller.seller_profile
    print(f"Seller profile exists: True")
    print(f"Seller profile is_active: {profile.is_active}")
except Exception as e:
    print(f"Seller profile exists: False ({type(e).__name__})")

# Get a listing from this seller
listing = Listing.objects.select_related(
    'owner',
    'owner__seller_profile',
    'store'
).filter(owner=active_seller).first()

if listing:
    print(f"\n=== Testing listing: {listing.title} (ID: {listing.id}) ===")
    print(f"Owner ID: {listing.owner_id}")
    print(f"Owner is_active: {listing.owner.is_active}")
    
    # Check seller profile access
    try:
        profile = listing.owner.seller_profile
        print(f"Seller profile accessible: True")
        print(f"Seller profile is_active: {profile.is_active}")
    except Exception as e:
        print(f"Seller profile accessible: False ({type(e).__name__})")
    
    # Check store
    if listing.store_id:
        print(f"Store ID: {listing.store_id}")
        try:
            store = listing.store
            print(f"Store accessible: True")
            print(f"Store is_active: {store.is_active}")
        except Exception as e:
            print(f"Store accessible: False ({type(e).__name__})")
    else:
        print("No store assigned")
    
    # Test is_ghost_listing
    print(f"\n=== is_ghost_listing result: {listing.is_ghost_listing} ===")
    print(f"Expected: False (seller is active)")
else:
    print(f"No listing found for seller {active_seller.username}")
