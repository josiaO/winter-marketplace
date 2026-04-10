
import os
import django
import sys

# Setup Django
# We need to find the correct path for settings. It's usually in the same dir as manage.py.
# Based on the file structure, it seems to be in 'backend/core/settings.py'
sys.path.append('/home/josiamosses/SmartDalali/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from decimal import Decimal
from django.contrib.auth import get_user_model
from commerce.models import Order
from escrow_engine.models import Transaction
from escrow_engine.services.payment import confirm_payment
from marketplace.models import Category
from listings.models import Listing

User = get_user_model()

def test_status_sync():
    print("--- Starting Status Sync Test ---")
    # 1. Get or create users
    buyer, _ = User.objects.get_or_create(username='test_buyer_1', defaults={'email': 'buyer@test.com'})
    seller, _ = User.objects.get_or_create(username='test_seller_1', defaults={'email': 'seller@test.com'})

    # 2. Get or create a category and listing
    category, _ = Category.objects.get_or_create(name='Test Category')
    listing, _ = Listing.objects.get_or_create(
        title='Test Item',
        owner=seller,
        defaults={
            'price': Decimal('1000.00'),
            'category': category,
            'is_published': True,
            'status': 'active'
        }
    )

    # 3. Create an order
    order = Order.objects.create(
        buyer=buyer,
        seller=seller,
        subtotal=Decimal('1000.00'),
        total_amount=Decimal('1100.00'),
        status='pending'
    )
    print(f"Created Order {order.id} with status: {order.status}")

    # 4. Create a transaction
    txn = Transaction.objects.create(
        amount=Decimal('1100.00'),
        source='marketplace',
        buyer_user=buyer,
        seller_user=seller,
        linked_order=order,
        status='CREATED'
    )
    print(f"Created Transaction {txn.reference} with status: {txn.status}")

    # 5. Simulate payment confirmation
    print("Confirming payment via confirm_payment()...")
    # This should move txn to PAID then HOLD, and now should move order to confirmed.
    from escrow_engine.state_machine import PaymentConfirmationSource

    confirm_payment(
        txn,
        gateway_reference='G_REF_123',
        actor=buyer,
        raw_payload={'script_manual': True},
        confirmation_source=PaymentConfirmationSource.ADMIN_MANUAL,
    )

    # 6. Verify statuses
    order.refresh_from_db()
    txn.refresh_from_db()

    print(f"Order status after payment: {order.status}")
    print(f"Transaction status after payment: {txn.status}")

    success = True
    if order.status != 'confirmed':
        print(f"❌ FAILURE: Order status is '{order.status}', expected 'confirmed'")
        success = False
    
    if txn.status != 'HOLD':
        print(f"❌ FAILURE: Transaction status is '{txn.status}', expected 'HOLD'")
        success = False

    if success:
        print("✅ SUCCESS: Status synchronization worked!")
    
    # Cleanup (optional, but good for multiple runs)
    # txn.delete()
    # order.delete()

if __name__ == '__main__':
    try:
        test_status_sync()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
