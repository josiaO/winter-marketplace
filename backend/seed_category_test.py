import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from catalog.models import Category, Attribute, AttributeOption
from marketplace.models import MarketplaceItem, ProductAttributeValue
from django.contrib.auth import get_user_model

User = get_user_model()

def seed_test_data():
    print("Seeding test data...")
    
    # Create a root category
    elec, _ = Category.objects.get_or_create(
        name="Electronics",
        slug="electronics",
        vertical="electronics"
    )
    
    # Create a leaf category
    phones, _ = Category.objects.get_or_create(
        name="Smartphones",
        slug="smartphones",
        parent=elec,
        vertical="electronics"
    )
    
    # Add attributes to leaf category
    brand, _ = Attribute.objects.get_or_create(
        category=phones,
        name="Brand",
        key="brand",
        field_type="select",
        is_required=True
    )
    
    AttributeOption.objects.get_or_create(attribute=brand, value="Apple")
    AttributeOption.objects.get_or_create(attribute=brand, value="Samsung")
    AttributeOption.objects.get_or_create(attribute=brand, value="Google")
    
    ram, _ = Attribute.objects.get_or_create(
        category=phones,
        name="RAM (GB)",
        key="ram",
        field_type="number",
        is_required=True
    )
    
    is_5g, _ = Attribute.objects.get_or_create(
        category=phones,
        name="Is 5G?",
        key="is_5g",
        field_type="boolean"
    )
    
    print(f"Created category: {phones.name}, Leaf: {phones.is_leaf()}")
    print(f"Created attributes: {Attribute.objects.filter(category=phones).count()}")

if __name__ == "__main__":
    seed_test_data()
