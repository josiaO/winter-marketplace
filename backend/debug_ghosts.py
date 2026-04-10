from django.contrib.auth import get_user_model
from listings.models import Listing
import django
import os
import sys

# Setup django
sys.path.append('/home/josiamosses/SmartDalali/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

User = get_user_model()
print('--- Active Sellers with Ghost Listings ---')
count = 0
for l in Listing.objects.select_related('owner', 'category').all():
    if l.is_ghost_listing:
        owner = l.owner
        if owner and owner.is_active:
            # Check if they have a seller profile
            has_profile = hasattr(owner, 'seller_profile')
            if has_profile and owner.seller_profile.is_active:
                vertical = l.category.vertical if (l.category and hasattr(l.category, 'vertical')) else 'N/A'
                print(f'ID: {l.id}, Title: {l.title}, Owner: {owner.username}, Store: {l.store_id}, Vertical: {vertical}, Category: {l.category.name if l.category else "None"}')
                count += 1
print(f'Total found: {count}')
