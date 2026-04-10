import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from core.models.category import Category

def seed():
    categories = [
        # Properties
        ('Apartment', 'property'),
        ('House', 'property'),
        ('Office', 'property'),
        ('Land', 'property'),
        
        # Vehicles
        ('Car', 'vehicle'),
        ('Motorcycle', 'vehicle'),
        ('Truck', 'vehicle'),
        
        # Electronics
        ('Smartphone', 'electronics'),
        ('Laptop', 'electronics'),
        ('Camera', 'electronics'),
        
        # Fashion
        ('Clothing', 'fashion'),
        ('Shoes', 'fashion'),
        ('Accessories', 'fashion'),
    ]

    for name, vertical in categories:
        slug = name.lower().replace(' ', '-')
        Category.objects.get_or_create(name=name, vertical=vertical, defaults={'slug': slug})
        print(f"Created category: {name} ({vertical})")

if __name__ == '__main__':
    seed()
