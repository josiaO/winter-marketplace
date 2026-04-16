from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models.signals import post_migrate, m2m_changed
from django.dispatch import receiver
from .models import Profile

@receiver(m2m_changed, sender=get_user_model().groups.through)
def create_seller_profile_on_group_add(sender, instance, action, pk_set, **kwargs):
    """Create a SellerProfile automatically when a user is added to the 'seller' group."""
    if action == "post_add":
        seller_group = Group.objects.filter(name="seller").first()
        if not seller_group:
            return
        if seller_group.pk in pk_set:
            # Ensure Profile exists
            Profile.objects.get_or_create(user=instance)
            # Create SellerProfile if it doesn't exist
            from marketplace.models import SellerProfile
            SellerProfile.objects.get_or_create(user=instance)


@receiver(post_migrate)
def create_default_groups(sender, **kwargs):
    """Create default groups if they don't exist.

    This runs after migrations. We keep it idempotent and simple: always
    ensure the groups exist.
    """
    Group.objects.get_or_create(name='seller')  # Seller/merchant role
    Group.objects.get_or_create(name='buyer')   # Normal buyer role