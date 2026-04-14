import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from trust.models import UserVerification
from marketplace.models import SellerProfile

print(f"Total UserVerification records: {UserVerification.objects.count()}")
for uv in UserVerification.objects.filter(id_status='verified')[:5]:
    print(f"Verified User: {uv.user.username}, ID Number: {uv.id_number}, Front: {uv.national_id_front}")

for sp in SellerProfile.objects.all()[:5]:
    print(f"Seller: {sp.store_name}, Status: {sp.verification_status}, Verified: {sp.is_verified}")
