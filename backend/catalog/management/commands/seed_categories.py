from django.core.management.base import BaseCommand
from catalog.models import Category, CategoryField

class Command(BaseCommand):
    help = 'Seeds the database with dynamic categories and specification fields for testing.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Seeding categories...")

        # 1. Computers and Accessories
        computers_main, _ = Category.objects.get_or_create(
            slug="computers-and-accessories",
            defaults={
                "name": "Computers and Accessories",
                "vertical": "electronics",
                "is_physical": True,
                "is_service": False,
                "icon": "computer"
            }
        )
        
        # Subcategories for Computers
        phones, _ = Category.objects.get_or_create(
            slug="phones",
            defaults={
                "name": "Phones",
                "parent": computers_main
            }
        )
        
        comps, _ = Category.objects.get_or_create(
            slug="computers",
            defaults={
                "name": "Computers",
                "parent": computers_main
            }
        )
        
        earphones, _ = Category.objects.get_or_create(
            slug="earphones",
            defaults={
                "name": "Earphones",
                "parent": computers_main
            }
        )

        # Specs for Phones
        CategoryField.objects.get_or_create(category=phones, field_name="brand", defaults={"field_label": "Brand", "field_type": "text", "required": True})
        CategoryField.objects.get_or_create(category=phones, field_name="model", defaults={"field_label": "Model", "field_type": "text", "required": True})
        CategoryField.objects.get_or_create(category=phones, field_name="storage", defaults={"field_label": "Storage Capacity", "field_type": "enum", "choices": ["64GB", "128GB", "256GB", "512GB", "1TB"], "required": True})
        CategoryField.objects.get_or_create(category=phones, field_name="ram", defaults={"field_label": "RAM", "field_type": "enum", "choices": ["4GB", "6GB", "8GB", "12GB", "16GB"], "required": True})

        # Specs for Computers
        CategoryField.objects.get_or_create(category=comps, field_name="brand", defaults={"field_label": "Brand", "field_type": "text", "required": True})
        CategoryField.objects.get_or_create(category=comps, field_name="processor", defaults={"field_label": "Processor", "field_type": "text", "required": True})
        CategoryField.objects.get_or_create(category=comps, field_name="ram", defaults={"field_label": "RAM", "field_type": "text", "required": True})
        CategoryField.objects.get_or_create(category=comps, field_name="storage", defaults={"field_label": "Storage", "field_type": "text", "required": True})

        # Specs for Earphones
        CategoryField.objects.get_or_create(category=earphones, field_name="brand", defaults={"field_label": "Brand", "field_type": "text", "required": True})
        CategoryField.objects.get_or_create(category=earphones, field_name="type", defaults={"field_label": "Type", "field_type": "enum", "choices": ["In-ear", "On-ear", "Over-ear"], "required": True})
        CategoryField.objects.get_or_create(category=earphones, field_name="wireless", defaults={"field_label": "Is Wireless?", "field_type": "boolean", "required": False})


        # 2. Vehicles
        vehicles_main, _ = Category.objects.get_or_create(
            slug="vehicles",
            defaults={
                "name": "Vehicles",
                "vertical": "vehicle",
                "is_physical": True,
                "is_service": False,
                "icon": "car"
            }
        )

        # Subcategories for Vehicles
        cars, _ = Category.objects.get_or_create(
            slug="cars",
            defaults={
                "name": "Cars",
                "parent": vehicles_main
            }
        )

        # Specs for Cars
        CategoryField.objects.get_or_create(category=cars, field_name="make", defaults={"field_label": "Make", "field_type": "text", "required": True})
        CategoryField.objects.get_or_create(category=cars, field_name="model", defaults={"field_label": "Model", "field_type": "text", "required": True})
        CategoryField.objects.get_or_create(category=cars, field_name="year", defaults={"field_label": "Year", "field_type": "integer", "required": True})
        CategoryField.objects.get_or_create(category=cars, field_name="transmission", defaults={"field_label": "Transmission", "field_type": "enum", "choices": ["Automatic", "Manual", "CVT"], "required": True})
        CategoryField.objects.get_or_create(category=cars, field_name="mileage", defaults={"field_label": "Mileage", "field_type": "integer", "unit": "km", "required": False})

        self.stdout.write(self.style.SUCCESS("Successfully seeded categories and specifications."))
